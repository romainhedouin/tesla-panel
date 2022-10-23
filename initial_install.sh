ssh-keygen -R 192.168.1.34
scp -r . pi@192.168.1.34:/home/pi
scp .bashrc pi@192.168.1.34:/home/pi
