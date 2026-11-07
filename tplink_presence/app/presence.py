"""Poll a TP-Link router's client list and publish presence to Home Assistant.

Each poll logs in, reads the client list in one request and logs out again, because
the router allows a single admin session. Failures never turn into "not_home": a
tracker whose router cannot be read is published as "unknown".
"""

import json
import os
import re
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

OPTIONS_FILE = "/data/options.json"
HA_API = "http://supervisor/core/api"
HEALTH_ENTITY = "sensor.tplink_presence_status"
HEARTBEAT_POLLS = 12  # log an unchanged successful poll about once an hour
MAX_BACKOFF = 1800

OK, UNREACHABLE, LOGIN_FAILED, UNEXPECTED = "ok", "unreachable", "login_failed", "unexpected_response"


class PollError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(event, level="info", **fields):
    print(json.dumps({"ts": now(), "level": level, "event": event, **fields}, default=str), flush=True)


def normalize_mac(mac):
    return re.sub(r"[^0-9a-f]", "", str(mac).lower())


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "device"


def tracker_entity(name):
    return f"device_tracker.tplink_{slug(name)}"


def classify(error, stage):
    """Map a library or network exception to a health kind."""
    name = type(error).__name__
    if name in ("ConnectionError", "Timeout", "ConnectTimeout", "ReadTimeout", "ConnectionRefusedError", "OSError", "SSLError"):
        return UNREACHABLE
    if stage == "login":
        return LOGIN_FAILED
    return UNEXPECTED


def scrub(text, secret):
    text = str(text)
    if secret:
        text = text.replace(secret, "***")
    return text[:300]


class RouterReader:
    """Reads the client list; keeps the detected client between polls."""

    def __init__(self, settings):
        self.settings = settings
        self.client = None
        self.client_class = None

    def _connect(self):
        from tplinkrouterc6u import TplinkRouterProvider

        s = self.settings
        self.client = TplinkRouterProvider.get_client(
            s["router_url"], s["password"], s["username"], None, s["verify_ssl"], s["timeout_seconds"]
        )
        self.client_class = type(self.client).__name__

    def read(self):
        """Returns the router's clients as dicts, raising PollError on failure."""
        stage = "login"
        try:
            if self.client is None:
                self._connect()
            self.client.authorize()
            stage = "fetch"
            status = self.client.get_status()
            clients = [
                {
                    "mac": normalize_mac(d.macaddr),
                    "ip": str(d.ipaddr),
                    "hostname": d.hostname,
                    "connection": getattr(d.type, "value", str(d.type)),
                    "active": bool(d.active),
                }
                for d in status.devices
            ]
        except Exception as error:
            self.client = None  # detect again next time, so a firmware change is picked up
            raise PollError(classify(error, stage), f"{type(error).__name__}: {scrub(error, self.settings['password'])}") from error
        try:
            self.client.logout()
        except Exception as error:
            log("logout_failed", level="warning", error=type(error).__name__)
        return clients


class HomeAssistant:
    def __init__(self, token, base=HA_API):
        self.token, self.base = token, base

    def put_state(self, entity_id, state, attributes):
        body = json.dumps({"state": state, "attributes": attributes}).encode()
        request = urllib.request.Request(
            f"{self.base}/states/{entity_id}",
            data=body,
            method="POST",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                pass
        except (urllib.error.URLError, OSError) as error:
            log("publish_failed", level="warning", entity=entity_id, error=type(error).__name__)


class Presence:
    def __init__(self, settings, reader, ha):
        self.settings, self.reader, self.ha = settings, reader, ha
        # (name, mac, hostname): a device matches on its MAC, else on its hostname
        self.tracked = [(t["name"], normalize_mac(t.get("mac") or ""), (t.get("hostname") or "").lower()) for t in settings["tracked"]]
        self.matched_by = {}
        self.failures = 0
        self.polls = 0
        self.last_success = None
        self.last_states = {}

    def poll(self):
        started = time.monotonic()
        try:
            clients = self.reader.read()
        except PollError as error:
            self.failures += 1
            duration = round((time.monotonic() - started) * 1000)
            log("poll_failed", level="error", kind=error.kind, error=str(error), failures=self.failures, duration_ms=duration)
            self._publish_health(error.kind, duration, str(error))
            for name, *_ in self.tracked:
                self._publish_tracker(name, "unknown", {})
            return
        duration = round((time.monotonic() - started) * 1000)
        by_mac = {c["mac"]: c for c in clients}
        by_hostname = {c["hostname"].lower(): c for c in clients if c["hostname"]}
        if self.settings.get("debug_clients"):
            log("clients", level="debug", clients=clients)
        self.failures = 0
        self.last_success = now()
        states = {}
        for name, mac, hostname in self.tracked:
            client, matched = by_mac.get(mac), "mac"
            if client is None and hostname:
                client, matched = by_hostname.get(hostname), "hostname"
            home = client is not None and client["active"]
            states[name] = "home" if home else "not_home"
            attributes = {"source_type": "router"}
            if client:
                attributes.update(mac=client["mac"], ip=client["ip"], hostname=client["hostname"], connection=client["connection"], matched_by=matched)
                if self.matched_by.get(name) != matched and matched == "hostname":
                    log("matched_by_hostname", level="warning", device=name, mac_seen=client["mac"], hint="the tracked MAC was not found; update it")
                self.matched_by[name] = matched
            self._publish_tracker(name, states[name], attributes)
        self._publish_health(OK, duration, None, clients_total=len(clients))
        self.polls += 1
        changed = states != self.last_states
        if changed or self.polls % HEARTBEAT_POLLS == 1:
            log("poll_ok", duration_ms=duration, clients=len(clients), client_class=self.reader.client_class, states=states, changed=changed)
        self.last_states = states

    def _publish_tracker(self, name, state, attributes):
        self.ha.put_state(tracker_entity(name), state, {"friendly_name": name, **attributes})

    def _publish_health(self, kind, duration, error, **extra):
        attributes = {
            "friendly_name": "TP-Link Presence status",
            "last_attempt": now(),
            "last_success": self.last_success,
            "duration_ms": duration,
            "consecutive_failures": self.failures,
            "client_class": self.reader.client_class,
            "error": error,
            **extra,
        }
        self.ha.put_state(HEALTH_ENTITY, kind, attributes)

    def delay(self):
        interval = self.settings["poll_interval_seconds"]
        if not self.failures:
            return interval
        return min(interval * 2 ** min(self.failures, 5), MAX_BACKOFF)  # gentle on a router that may lock out bad logins

    def shutdown(self):
        for name, *_ in self.tracked:
            self.ha.put_state(tracker_entity(name), "unavailable", {"friendly_name": name})
        self.ha.put_state(HEALTH_ENTITY, "unavailable", {"friendly_name": "TP-Link Presence status"})


def main():
    with open(OPTIONS_FILE) as f:
        settings = json.load(f)
    log("start", router=settings["router_url"], tracked=[t["name"] for t in settings["tracked"]], interval=settings["poll_interval_seconds"])
    if not settings["password"]:
        sys.exit("Set the router password in the add-on options.")
    for device in settings["tracked"]:
        if not (device.get("mac") or device.get("hostname")):
            sys.exit(f"Tracked device {device['name']!r} needs a mac or a hostname.")
    presence = Presence(settings, RouterReader(settings), HomeAssistant(os.environ["SUPERVISOR_TOKEN"]))
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        presence.poll()
        stop.wait(presence.delay())
    presence.shutdown()
    log("stop")


if __name__ == "__main__":
    main()
