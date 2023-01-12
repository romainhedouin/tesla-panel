import bluetooth
import os
import signal
from time import sleep

pid_file = "/home/pi/bt_server.pid"

def logger(command):
    print(command)
    with open("/home/pi/bt_server.log", "w") as f:
        f.write(command)
        f.write("\n")

def receive_data(client_sock):
    received_data = client_sock.recv(1024)
    logger("[+] Received: %s" % received_data)
    client_sock.send("OK")
    return received_data

def legacy_command(client_sock, data):
    data = receive_data(client_sock)
    if os.path.exists("/home/pi/src/" + data.decode("utf-8") + ".sh"):
        os.popen("sh /home/pi/src/" + data.decode("utf-8") + ".sh")
        logger("sh /home/pi/src/%s.sh" % data.decode("utf-8"))

def image_command(client_sock, data):
    data = receive_data(client_sock)
    ## Save the data to a temporary file
    with open("/home/pi/temporary.ppm", "wb") as f:
        f.write(data)
    ## Display the image for 3 seconds, then kill the process
    command = "./rpi-rgb-led-matrix/examples-api-use/demo --led-no-hardware-pulse /home/pi/temporary.ppm --led-gpio-mapping=adafruit-hat --led-cols=64 -D 1 &"
    os.popen(command)
    logger("Running: " + command)
    sleep(3)
    os.popen("killall demo")
    logger("Running: killall demo")

if __name__ == '__main__':

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

    logger("[+] Listening for incoming connections on RFCOMM channel " + port.__str__())

    client_sock, client_info = server_sock.accept()

    while True:
        data = receive_data(client_sock)
        if len(data) == 0:
            logger("[-] No data received")
        else:
            if data.decode("utf-8") == "legacy_command":
                logger("[+] Received legacy command")
                legacy_command(client_sock, data)
            if data.decode("utf-8") == "image_command":
                logger("[+] Received image command")
                image_command(client_sock, data)
        if data == "quit":
            break

    logger("[+] Disconnected")

    client_sock.close()
    server_sock.close()
    logger("[+] All done")
