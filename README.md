# tesla-panel

Pi-side receiver for the 64×32 RGB LED matrix mounted in the car. Listens
over Bluetooth RFCOMM for commands from the
[TeslaLED](https://github.com/romainhedouin/TeslaLED) Android app and drives
the panel via [rpi-rgb-led-matrix](rpi-rgb-led-matrix/)'s Python bindings.

`rpi-rgb-led-matrix/` is a git submodule pointing straight at
[hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix)
(no local patches to carry - if that ever changes, fork it first rather
than patching the submodule in place). Clone this repo with `git clone
--recurse-submodules`, or run `git submodule update --init` afterwards if
you already cloned without it - `deploy.sh` needs it checked out locally
to have anything to rsync to the Pi.

`bt_server.py` is the entry point, wiring together `protocol.py` (the wire
protocol - hardware/transport agnostic, covered by `tests/`), `panel.py`
(the RGBMatrix hardware wrapper) and `bt_profile.py` (BlueZ D-Bus service
registration).

There is no CI/CD deploying to the Pi itself: these files are copied by hand
onto the Pi's home directory (`/home/pi/`) and run via systemd. **A protocol
or behavior change isn't live until you actually redeploy the changed file
to the Pi** - nothing in this repo does that for you, and nothing checks
that the Pi is still in sync with what's committed here. `tests/` (`python3
-m pytest tests/`) only exercises `protocol.py`, so it catches wire-format
regressions but nothing hardware- or Bluetooth-related.

## Raspberry Pi OS install

Only needed once, on a fresh/replacement SD card, before `pi_side_install.sh`.
Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/):

1. Choose **Raspberry Pi OS Lite (64-bit)** as the OS.
2. Choose the SD card as the storage device - **be very careful you've
   selected the right one**, this erases it.
3. Follow the app's setup prompts (hostname, user, SSH, WiFi, locale) and
   write.

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

## Bluetooth service registration

`bt_profile.py` registers the RFCOMM service with BlueZ over D-Bus
(`org.bluez.ProfileManager1.RegisterProfile`), not PyBluez's
`advertise_service()`. That's a hard requirement, not a style choice:
current BlueZ (5.82+, what Debian 13/trixie ships) removed the legacy
`/var/run/sdp` socket interface that `advertise_service()` (and `sdptool`)
depend on, so both fail unconditionally with `[Errno 2] No such file or
directory` on this OS. And it has to be real SDP, not a shortcut around it -
the Android app connects via `createRfcommSocketToServiceRecord(UUID)`,
which looks up the RFCOMM channel through an actual SDP query at connect
time, so the Pi genuinely needs a working SDP record, not just an open
socket on a known channel.

Registering through `ProfileManager1` also changes the connection-handling
model: BlueZ owns the listening socket entirely and calls our exported
`Profile1.NewConnection(device, fd, properties)` once per incoming
connection with an already-connected fd, so there's no `listen()`/`accept()`
in this codebase at all. Needs `python3-dbus` and `python3-gi` (installed by
`pi_side_install.sh`).

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
- On a fresh Pi: `./deploy.sh` from this repo copies it onto the Pi, then
  `ssh teslapi` and run `./pi_side_install.sh` there (packages, sudoers,
  compiling `rpi-rgb-led-matrix` and its Python bindings, installing the
  systemd unit). Safe to re-run - most of its steps are no-ops if already done.

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
