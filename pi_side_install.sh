sudo apt-get update
sudo apt-get install php emacs dnsmasq chkconfig lsof
sudo raspi-config nonint do_wifi_country FR
sudo chmod 755 startup_bot.sh
make -C /home/pi/rpi-rgb-led-matrix/
sudo rm -rf initial_install.sh Pictures Downloads Desktop Public Videos Music Templates Documents
sudo curl -sL https://install.raspap.com | bash -s -- --yes
sudo systemctl stop lighttpd.service && sudo systemctl disable lighttpd.service
#sudo chown root tesla_bot && sudo chmod 755 tesla_bot && sudo mv tesla_bot /etc/init.d/

## cp banner_add_hosts /etc/
## then go edit /etc/dnsmasq.conf to remove the hashtag before `addn-hosts=/etc/banner_add_hosts`
## You may need to `sudo systemctl stop lighttpd`