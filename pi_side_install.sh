## This removes the need for any password in the future when calling sudo
sudo echo "pi ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

## Install the required packages and dependencies
sudo apt-get update
sudo apt-get install emacs python3-pip python3-dev libpython3-dev bluetooth libbluetooth-dev bluez-tools
sudo raspi-config nonint do_wifi_country FR
sudo python3 -m pip install pybluez
sudo rm -rf initial_install.sh Pictures Downloads Desktop Public Videos Music Templates Documents

## Compile the C++ library for the LED matrix, plus the Python bindings
## bt_server.py imports directly (rgbmatrix) - this drives the panel through
## the library's own frame buffer instead of shelling out to a compiled demo
## binary per image, which is what makes updates flicker-free.
make -C /home/pi/rpi-rgb-led-matrix/
make -C /home/pi/rpi-rgb-led-matrix/bindings/python build-python PYTHON=$(which python3)
sudo make -C /home/pi/rpi-rgb-led-matrix/bindings/python install-python PYTHON=$(which python3)

sudo mv conf/dbus-org.bluez.service /etc/systemd/system/
sudo mv conf/teslabot.service /etc/systemd/system/
sudo mv conf/wpa_supplicant.conf /etc/wpa_supplicant/
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
sudo systemctl enable teslabot.service
sudo systemctl start teslabot.service
sudo sdptool add SP

#sudo curl -sL https://install.raspap.com | bash -s -- --yes
#sudo systemctl stop lighttpd.service && sudo systemctl disable lighttpd.service
#sudo rm -rf /etc/init.d/apache2
#sudo chown root tesla_bot && sudo chmod 755 tesla_bot && sudo mv tesla_bot /etc/init.d/

## cp banner_add_hosts /etc/
## then go edit /etc/dnsmasq.conf to remove the hashtag before `addn-hosts=/etc/banner_add_hosts`
## You may need to `sudo systemctl stop lighttpd`