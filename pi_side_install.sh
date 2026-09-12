#!/bin/bash
set -e

## Bootstrap passwordless sudo. Every later `sudo` in this script - and
## teslabot/bt_server.py at runtime, launched by systemd with no TTY - assumes
## this already works, so it has to happen first and has to actually succeed.
## `sudo echo foo >> /etc/sudoers` is a classic trap: the `>>` redirect runs in
## this unprivileged shell, not under sudo, so it silently fails to write to a
## root-owned file. Writing through `sudo tee` avoids that, and `visudo -c`
## catches a syntax mistake before it can lock out sudo entirely.
if ! sudo -n true 2>/dev/null; then
  read -s -p "sudo password for $(whoami) (used once, to set up passwordless sudo): " SUDO_PW
  echo
  echo "$SUDO_PW" | sudo -S true
fi
echo "pi ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/010-pi-nopasswd > /dev/null
sudo chmod 440 /etc/sudoers.d/010-pi-nopasswd
sudo visudo -c

## Install the required packages and dependencies.
## python3-dbus, python3-gi: bt_server.py registers its RFCOMM/SDP service
##   with BlueZ over D-Bus (org.bluez.ProfileManager1) - see bt_profile.py.
##   PyBluez's old advertise_service()/sdptool-based approach no longer works
##   at all on this BlueZ version (5.82+ removed the legacy /var/run/sdp
##   socket interface both of those depend on).
## bluez-tools: provides bt-agent, used by ./teslabot for pairing.
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

sudo mv conf/teslabot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
sudo systemctl enable teslabot.service
sudo systemctl start teslabot.service

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

rm -f /home/pi/deploy.sh
