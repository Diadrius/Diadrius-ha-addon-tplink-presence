# TP-Link Presence

Polls your TP-Link router's client list and publishes presence to Home Assistant.

## Options

| Option | Meaning |
| --- | --- |
| `router_url` | Router address, e.g. `http://192.168.0.1` |
| `username` | Usually `admin`. Many models only ask for a password, and the username is then unused |
| `password` | The router's local admin password |
| `poll_interval_seconds` | Time between polls (60 to 3600). Each poll logs you out of the router's web page |
| `timeout_seconds` | Per-request timeout towards the router |
| `verify_ssl` | Check the router's HTTPS certificate (most routers use a self-signed one) |
| `debug_clients` | Log every client the router reports on each poll, to find a device's MAC. Turn off afterwards: the list contains all your devices |
| `tracked` | Devices to report: a `name` and the device's Wi-Fi `mac` |

Use the address the phone shows under Wi-Fi settings. Phones that use a private Wi-Fi
address should use a fixed one for your home network, or the MAC will change.

## Entities

- `device_tracker.tplink_<name>`: `home`, `not_home`, or `unknown` when the router
  could not be read. Attributes: IP, hostname and connection type.
- `sensor.tplink_presence_status`: `ok`, `unreachable`, `login_failed` or
  `unexpected_response`. Attributes: `last_success`, `last_attempt`, `duration_ms`,
  `consecutive_failures`, `client_class`, `error`.

Both become `unavailable` when the add-on stops. Trackers set through the states API are
not kept across a Home Assistant restart until the next poll.

Automations should treat `unknown`, `unavailable` and a stale `last_success` as
"don't know", not as "away".

## Logs

JSON lines. Events: `start`, `poll_ok` (on changes and about hourly), `poll_failed`
(with `kind`, error text and duration), `publish_failed`, `logout_failed`, `stop`.
After a router firmware update, check `poll_failed` entries with `unexpected_response`.

After repeated failures the add-on polls less often (up to every 30 minutes), so a wrong
password doesn't hammer the router's login.
