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

rm -f /home/pi/deploy.sh
