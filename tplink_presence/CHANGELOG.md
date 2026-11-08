# Changelog

## 0.1.4

- The tracker also publishes the device's `signal` (dBm), `tx_rate`, `rx_rate` and `band` as attributes when the router reports them. No extra router requests; a missing reading is simply left out.

## 0.1.3

- Optional faster polling during an initial device absence, returning to the normal interval after the confirmation window or when the device returns. Failures retain the existing backoff.

## 0.1.2

- Tracked devices can also be matched by `hostname`, as a fallback when the MAC is not found (e.g. a rotated private address).

## 0.1.1

- `debug_clients` option: logs the full client list each poll, to find a device's MAC. Off by default.

## 0.1.0

- First version: polls the client list, publishes a tracker per chosen device and a health sensor.
