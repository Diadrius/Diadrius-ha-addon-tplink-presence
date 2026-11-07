# TP-Link Presence add-on

A public, generic Home Assistant add-on. It reads a TP-Link router's client list and
publishes home/away trackers plus a health sensor. Anyone should be able to install and
use it; nothing in the repo may depend on one person's setup.

## Rules

- **Never commit secrets or personal data**: router passwords, tokens, real MAC
  addresses, IP addresses, hostnames, or names of people and devices. Tests and docs use
  fake values (`AA:BB:CC:00:11:22`, `10.0.0.5`).
- **Stay generic.** No references to any private repo, house, or heating logic. Behavior
  is configured through add-on options, not hard-coded.
- **Never log the password. Log the full client list only when the user turns on `debug_clients`.** Log error types, timings and
  response shape only. Scrub secrets from error text.
- **Fail safe.** Any failure to read the router publishes `unknown`, never `not_home`.
- Keep the router load low: one login, one client-list request, then logout.
- The router allows a single admin session; do not poll faster than the 60 s minimum.

## Layout

- `tplink_presence/`: the add-on (`config.yaml`, `Dockerfile`, `app/presence.py`, `DOCS.md`).
- `tests/`: unit tests with fake data (`python3 -m unittest discover -s tests`).
- Bump `version` in `tplink_presence/config.yaml` and add a CHANGELOG entry for every
  change that should reach installed copies; Supervisor updates only on a version change.
- `dev` is for testing changes on a real instance; `main` is what users install.
- Router login and parsing come from `tplinkrouterc6u` (pinned in `requirements.txt`).
  Update the pin deliberately and test.
