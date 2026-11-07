# TP-Link Presence for Home Assistant

A Home Assistant add-on that reads a TP-Link router's client list and reports whether
chosen devices (usually phones) are home. It works from the router's own view of who
is connected, so it also covers bands and sleeping phones that a network scan misses.

I built this for my own setup and share it in case it helps someone else. It is
unofficial and not affiliated with or endorsed by TP-Link.

## Why this one

- **Light on the router and the Pi.** Each poll logs in, reads the client list in a
  single request and logs out. The default is every 5 minutes.
- **Safe failure.** If the router can't be read (wrong password, firmware change,
  network trouble), a tracker becomes `unknown`, never `not_home`.
- **Visible health.** `sensor.tplink_presence_status` reports `ok`, `unreachable`,
  `login_failed` or `unexpected_response`, with the last success time and poll duration.
- **Useful logs.** One JSON line per event, with error types and timings. Passwords and
  client lists are never logged.

Login and parsing use the community library
[`tplinkrouterc6u`](https://github.com/AlexandrErohin/TP-Link-Archer-C6U), so the
supported models are those it supports. Tested: Archer BE550 (see the table below).

| Model | Tested |
| --- | --- |
| Archer BE550 | yes (client type `TplinkRouterSG`) |

## Install

1. In Home Assistant: Settings, Add-ons, Add-on store, menu, Repositories, and add
   `https://github.com/Diadrius/Diadrius-ha-addon-tplink-presence`.
2. Install **TP-Link Presence**, fill in the options (see [DOCS.md](tplink_presence/DOCS.md))
   and start it.

## Development

`python3 -m unittest discover -s tests` runs the tests. They use fake data and need no
router. Contributions that keep the add-on generic are welcome.

MIT licensed.
