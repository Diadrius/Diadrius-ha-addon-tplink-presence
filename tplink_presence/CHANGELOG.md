# Changelog

## 0.1.2

- Tracked devices can also be matched by `hostname`, as a fallback when the MAC is not found (e.g. a rotated private address).

## 0.1.1

- `debug_clients` option: logs the full client list each poll, to find a device's MAC. Off by default.

## 0.1.0

- First version: polls the client list, publishes a tracker per chosen device and a health sensor.
