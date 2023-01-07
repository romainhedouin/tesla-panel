ssh-keygen -R 192.168.1.44
scp -r . pi@192.168.1.44:/home/pi
scp .bashrc pi@192.168.1.44:/home/pi
