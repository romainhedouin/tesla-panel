"""
A simple Python script to receive messages from a client over
Bluetooth using Python sockets (with Python 3.3 or above).
"""

import socket
import os
import signal
import subprocess

def enable_bluetooth():
    subprocess.run(["bluetoothctl", "power", "on"])

def make_discoverable():
    subprocess.run(["bluetoothctl", "discoverable", "on"])

pid_file = "/home/pi/bt_server.pid"

enable_bluetooth()
make_discoverable()

# check if the pid file exists
if os.path.exists(pid_file):
    # the pid file exists, so read the process ID from the file
    with open(pid_file, 'r') as f:
        pid = int(f.read())
    
    # try to kill the process
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

hostMACAddress = 'B8:27:EB:A5:89:A8' # The MAC address of a Bluetooth adapter on the server. The server might have multiple Bluetooth adapters.
port = 5
backlog = 1
size = 1024
s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
s.bind((hostMACAddress,port))
s.listen(backlog)
try:
    # store the current process ID in the pid file
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    client, address = s.accept()
    while 1:
        data = client.recv(size)
        if data:
            print(data)
            if os.path.exists("/home/pi/src/" + data.decode("utf-8") + ".sh"):
                os.popen("sh /home/pi/src/" + data.decode("utf-8") + ".sh")
                os.popen("echo " + "sh /home/pi/src/" + data.decode("utf-8") + ".sh" + " >> /home/pi/bt_server.log")
            client.send(data)
except:	
    print("Closing socket")	
    client.close()
    s.close()