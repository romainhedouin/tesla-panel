ssh-keygen -R 192.168.1.36
scp -r . pi@192.168.1.36:/home/pi
scp .bashrc pi@192.168.1.36:/home/pi