import bluetooth
import os
import signal

pid_file = "/home/pi/bt_server.pid"

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

server_sock=bluetooth.BluetoothSocket( bluetooth.RFCOMM )

server_sock.bind(("",bluetooth.PORT_ANY))
server_sock.listen(1)

port = server_sock.getsockname()[1]

uuid = "00001101-0000-1000-8000-00805F9B34FB"

bluetooth.advertise_service( server_sock, "My Bluetooth Server",
                   service_id = uuid,
                   service_classes = [ uuid, bluetooth.SERIAL_PORT_CLASS ],
                   profiles = [ bluetooth.SERIAL_PORT_PROFILE ])

print("[+] Listening for incoming connections on RFCOMM channel %d" % port)

client_sock, client_info = server_sock.accept()
print("[+] Accepted connection from ", client_info)

while True:
    data = client_sock.recv(1024)
    if len(data) == 0:
        print("[-] No data received")
    else:
        print("[+] Received: %s" % data)
        if os.path.exists("/home/pi/src/" + data.decode("utf-8") + ".sh"):
            os.popen("sh /home/pi/src/" + data.decode("utf-8") + ".sh")
            os.popen("echo " + "sh /home/pi/src/" + data.decode("utf-8") + ".sh" + " >> /home/pi/bt_server.log")
    client_sock.send(data)
    if data == "quit":
        break

print("[+] Disconnected")

client_sock.close()
server_sock.close()
print("[+] All done")
