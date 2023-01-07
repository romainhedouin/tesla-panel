import socket

serverMACAddress = 'B8:27:EB:A5:89:A8'
s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
UUID = "00001101-0000-1000-8000-00805F9B34FB"
s.connect((serverMACAddress, 1))
while True:
    s.send(input("Enter your message: ").encode())
    data = s.recv(1024)
    print("received [%s]" % data)
    if data == b'quit':
        break
s.close()
