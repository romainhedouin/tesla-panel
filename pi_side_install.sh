#!/bin/bash
set -e

## Install the required packages and dependencies.
## python3-dbus, python3-gi: bt_server.py registers its RFCOMM/SDP service
##   with BlueZ over D-Bus (org.bluez.ProfileManager1) - see bt_profile.py.
##   PyBluez's old advertise_service()/sdptool-based approach no longer works
##   at all on this BlueZ version (5.82+ removed the legacy /var/run/sdp
##   socket interface both of those depend on).
## bluez-tools: provides bt-agent, used by teslabot-agent.service for pairing.
## python3-pil: not used by our code directly, but rpi-rgb-led-matrix's
##   Python bindings unconditionally compile against Pillow's internal
##   Imaging.h (bindings/python/rgbmatrix/shims/pillow.c) - apt's python3-pil
##   is what puts that header under /usr/include/python3.13/.
## cmake, ninja-build: rpi-rgb-led-matrix's Python bindings now build via
##   CMake + scikit-build-core (see below) instead of a hand-rolled Makefile.
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev libpython3-dev \
  bluetooth libbluetooth-dev bluez-tools \
  python3-dbus python3-gi python3-pil cmake ninja-build
sudo raspi-config nonint do_wifi_country FR

## Build the C++ library and Python bindings. bt_server.py imports directly
## (rgbmatrix) - this drives the panel through the library's own frame
## buffer instead of shelling out to a compiled demo binary per image,
## which is what makes updates flicker-free.
##
## `pip install .` from the repo root does the whole thing now (upstream
## dropped the old setup.py/cythonize-by-hand approach for a CMakeLists.txt
## driven by scikit-build-core): it fetches a matching Cython into an
## isolated build env, regenerates core.cpp/graphics.cpp from the actual
## core.pyx/graphics.pyx source, and compiles/installs everything. Nothing
## here is a stale committed artifact - see rpi-rgb-led-matrix/.gitignore.
## --break-system-packages: this Pi runs a single dedicated system Python
## for teslabot (no venv, launched by systemd as root), so PEP 668's
## "externally managed environment" guard has to be overridden rather than
## worked around with a venv nothing else here uses.
sudo python3 -m pip install --break-system-packages /home/pi/rpi-rgb-led-matrix

## Bluetooth stays discoverable indefinitely instead of BlueZ's default 180s
## timeout - teslabot-discoverable.service only runs `discoverable on` once
## at boot, so without this it'd silently stop being discoverable 3 minutes
## after every boot. Idempotent: uncomments the (commented-out, by default on
## Raspberry Pi OS) key if present, otherwise appends it under [General].
set_bluetooth_config() {
  local file="/etc/bluetooth/main.conf"
  if grep -qE '^#?DiscoverableTimeout' "$file"; then
    sudo sed -i -E 's/^#?DiscoverableTimeout.*/DiscoverableTimeout = 0/' "$file"
  else
    sudo sed -i '/^\[General\]/a DiscoverableTimeout = 0' "$file"
  fi
}
set_bluetooth_config

## teslabot.service (bt_server.py, needs root for GPIO), teslabot-agent.service
## (bt-agent pairing) and teslabot-discoverable.service (power on + stay
## discoverable) replace the old single `teslabot` bash script's three
## hand-rolled respawn loops - systemd's own Restart=always/RestartSec
## supervises each independently, with per-unit status/logs via
## `systemctl status`/`journalctl -u`.
sudo cp conf/teslabot.service conf/teslabot-agent.service conf/teslabot-discoverable.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
sudo systemctl enable --now teslabot-discoverable.service teslabot-agent.service teslabot.service

## Lets deploy.sh restart teslabot.service over a plain ssh command (no PTY)
## after pushing new code, without prompting for a password each time. Scoped
## to just that one command rather than a blanket NOPASSWD - not because this
## Pi needs the security, but because that's all deploy.sh actually needs.
echo "pi ALL=(root) NOPASSWD: /usr/bin/systemctl restart teslabot.service" | sudo tee /etc/sudoers.d/010-teslabot-restart > /dev/null
sudo chmod 440 /etc/sudoers.d/010-teslabot-restart
sudo visudo -c

## Power tuning. This Pi is headless in a car - no HDMI/camera/DSI display is
## ever connected and nothing uses onboard audio - so disable the hardware
## auto-detect/circuits for them outright. Idempotent: replaces the line if
## config.txt already has one (from raspi-config or a prior run of this
## script) instead of appending a duplicate that would conflict with it.
## PWR/ACT LEDs are deliberately left alone - keep those.
set_boot_config() {
  # $1: prefix identifying the existing line to replace (e.g. "dtparam=audio=")
  # $2: the full replacement line
  local match_prefix="$1" new_line="$2" file="/boot/firmware/config.txt"
  if grep -q "^${match_prefix}" "$file"; then
    sudo sed -i "s|^${match_prefix}.*|${new_line}|" "$file"
  else
    echo "${new_line}" | sudo tee -a "$file" > /dev/null
  fi
}
set_boot_config "dtparam=audio=" "dtparam=audio=off"
set_boot_config "camera_auto_detect=" "camera_auto_detect=0"
set_boot_config "display_auto_detect=" "display_auto_detect=0"

## eth0 is never plugged in on this install (WiFi + Bluetooth only), but
## unlike audio/camera/display this one's a judgment call rather than a clear
## win - it shares silicon with the external USB ports' hub, so how much
## power bringing it down actually saves is uncertain. Ask instead of
## assuming; an empty/non-interactive answer (e.g. this script re-run
## non-interactively over ssh) defaults to leaving it alone.
read -p "Disable the unused eth0 (Ethernet) interface? Small, uncertain power saving [y/N] " DISABLE_ETH
if [[ "$DISABLE_ETH" =~ ^[Yy]$ ]]; then
  sudo tee /etc/systemd/system/disable-eth0.service > /dev/null <<'UNIT'
[Unit]
Description=Bring down unused eth0 (headless project - WiFi + Bluetooth only)
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/ip link set eth0 down
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  sudo systemctl enable --now disable-eth0.service
else
  sudo systemctl disable --now disable-eth0.service 2>/dev/null || true
  sudo rm -f /etc/systemd/system/disable-eth0.service
fi
