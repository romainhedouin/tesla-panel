# tesla-panel

Pi-side receiver for the 64×32 RGB LED matrix mounted in the car. Listens
over Bluetooth RFCOMM for commands from the
[TeslaLED](https://github.com/romainhedouin/TeslaLED) Android app and drives
the panel via [rpi-rgb-led-matrix](rpi-rgb-led-matrix/)'s Python bindings.

There is no CI/CD here: `bt_server.py` and `teslabot` are copied by hand onto
the Pi's home directory (`/home/pi/`) and run via systemd. **A protocol or
behavior change isn't live until you actually redeploy the changed file to
the Pi** - nothing in this repo does that for you, and nothing checks that
the Pi is still in sync with what's committed here.

## Wire protocol

`bt_server.py` speaks a length-prefixed binary protocol, matched byte-for-byte
by the Android app's `BluetoothClient`/`AGENTS.md`:

```
[1 byte command type][4 bytes big-endian payload length][payload]
```

followed by a single status byte in response (`0x00` = OK, anything else =
error). Command types (kept in sync with the Android app's constants of the
same name):

| Command                 | Value | Payload                                  |
|--------------------------|-------|-------------------------------------------|
| `COMMAND_IMAGE`           | 0     | a 64×32 P6 PPM frame                       |
| `COMMAND_KILL`            | 2     | none - clears the panel                    |
| `COMMAND_SET_BRIGHTNESS`  | 3     | 1 byte, 1-100                              |

RFCOMM is a reliable ordered stream, so the length prefix is all that's
needed to find message boundaries - no sentinel value, no per-chunk acks.

The matrix and its offscreen canvas are created once at process start and
live for the whole process; every `COMMAND_IMAGE`/`COMMAND_KILL` is an atomic
`SwapOnVSync` onto that same canvas rather than a process kill/respawn, which
is what keeps updates flicker-free.

## Deployment

- `teslabot` (bash) is the actual systemd entry point (`conf/teslabot.service`):
  it keeps Bluetooth powered on and discoverable, keeps a pairing agent
  (`bt-agent -c NoInputNoOutput`) registered, and respawns `bt_server.py` if
  it ever exits.
- Pairing a new phone with the Pi silently fails (no error anywhere, not even
  in `bluetoothctl paired-devices`) unless that pairing agent is running -
  if pairing won't complete, check `systemctl status teslabot` before
  suspecting anything else.
- The Pi's Bluetooth MAC is hardcoded on the Android side
  (`BluetoothClient.findDevice()`); replacing the Pi means updating that
  constant and rebuilding the app.
- `pi_side_install.sh` is the from-scratch bootstrap (packages, sudoers,
  compiling `rpi-rgb-led-matrix` and its Python bindings, installing the
  systemd unit). It's meant to be re-run in full only on a fresh Pi image -
  most of its steps (package installs, sudoers) are no-ops if already done.

## Troubleshooting

- **Colored static/noise instead of the actual image** is a GPIO-timing or
  wiring issue, not a protocol/software bug - reproduce it with the LED
  matrix library's own test patterns (`rpi-rgb-led-matrix/examples-api-use`)
  with no Bluetooth involved at all before looking anywhere else.
- **Pairing never completes**: see the pairing-agent note above.
- **Panel doesn't update / commands seem to hang**: check `bt_server.log` in
  `/home/pi/` and `journalctl -u teslabot` - a command whose handler raises
  gets logged and answered with an error status rather than silently
  dropped, so a hang usually means the client never got as far as sending
  the header/payload, not a wedged server.
