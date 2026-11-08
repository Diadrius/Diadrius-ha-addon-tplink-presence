import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tplink_presence" / "app"))
import presence  # noqa: E402

SETTINGS = {
    "router_url": "http://router.invalid",
    "username": "admin",
    "password": "hunter2",
    "poll_interval_seconds": 300,
    "timeout_seconds": 20,
    "verify_ssl": False,
    "tracked": [{"name": "Test Phone", "mac": "AA:BB:CC:00:11:22"}],
}


class FakeReader:
    client_class = "FakeRouter"

    def __init__(self, result):
        self.result = result

    def read(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeHA:
    def __init__(self):
        self.states = {}

    def put_state(self, entity_id, state, attributes):
        self.states[entity_id] = (state, attributes)


def phone(active=True):
    return {"mac": "aabbcc001122", "ip": "10.0.0.5", "hostname": "phone", "connection": "host_6g", "active": active}


class PresenceTest(unittest.TestCase):
    def run_poll(self, result):
        ha = FakeHA()
        p = presence.Presence(SETTINGS, FakeReader(result), ha)
        p.poll()
        return p, ha

    def test_home_when_listed_and_active(self):
        _, ha = self.run_poll([phone()])
        self.assertEqual(ha.states["device_tracker.tplink_test_phone"][0], "home")
        self.assertEqual(ha.states[presence.HEALTH_ENTITY][0], "ok")

    def test_not_home_when_missing_or_inactive(self):
        for clients in ([], [phone(active=False)]):
            _, ha = self.run_poll(clients)
            self.assertEqual(ha.states["device_tracker.tplink_test_phone"][0], "not_home")

    def test_failure_is_unknown_never_not_home(self):
        p, ha = self.run_poll(presence.PollError(presence.UNREACHABLE, "boom"))
        self.assertEqual(ha.states["device_tracker.tplink_test_phone"][0], "unknown")
        self.assertEqual(ha.states[presence.HEALTH_ENTITY][0], "unreachable")
        self.assertEqual(p.failures, 1)

    def test_backoff_grows_and_resets(self):
        p, _ = self.run_poll(presence.PollError(presence.LOGIN_FAILED, "bad"))
        self.assertEqual(p.delay(), 600)
        p.reader = FakeReader([])
        p.poll()
        self.assertEqual(p.delay(), 300)

    def test_confirmation_polling_window_and_return(self):
        clock = [0]
        settings = {**SETTINGS, "poll_interval_seconds": 120,
                    "absence_confirmation_seconds": 360,
                    "confirmation_poll_interval_seconds": 60}
        reader = FakeReader([phone()])
        p = presence.Presence(settings, reader, FakeHA(), clock=lambda: clock[0])
        p.poll()
        self.assertEqual(p.delay(), 120)
        reader.result = []
        p.poll()
        self.assertEqual(p.delay(), 60)
        clock[0] = 359
        p.poll()
        self.assertEqual(p.delay(), 60)
        clock[0] = 360
        p.poll()
        self.assertEqual(p.delay(), 120)
        reader.result = [phone()]
        p.poll()
        reader.result = []
        p.poll()
        self.assertEqual(p.delay(), 60)
        reader.result = presence.PollError(presence.UNREACHABLE, "boom")
        p.poll()
        self.assertEqual(p.delay(), 240)
        reader.result = [phone()]
        p.poll()
        self.assertEqual(p.delay(), 120)

    def test_classify(self):
        self.assertEqual(presence.classify(ConnectionError(), "login"), presence.UNREACHABLE)
        self.assertEqual(presence.classify(Exception("x"), "login"), presence.LOGIN_FAILED)
        self.assertEqual(presence.classify(KeyError("x"), "fetch"), presence.UNEXPECTED)

    def test_hostname_fallback_when_mac_changes(self):
        settings = {**SETTINGS, "tracked": [{"name": "Test Phone", "mac": "AA:BB:CC:00:11:22", "hostname": "Phone"}]}
        ha = FakeHA()
        client = {**phone(), "mac": "0000000000ff"}
        presence.Presence(settings, FakeReader([client]), ha).poll()
        state, attributes = ha.states["device_tracker.tplink_test_phone"]
        self.assertEqual((state, attributes["matched_by"]), ("home", "hostname"))

    def test_scrub_hides_password(self):
        self.assertNotIn("hunter2", presence.scrub("failed with hunter2", "hunter2"))

    def test_shutdown_marks_unavailable(self):
        p, ha = self.run_poll([phone()])
        p.shutdown()
        self.assertEqual(ha.states[presence.HEALTH_ENTITY][0], "unavailable")


if __name__ == "__main__":
    unittest.main()
