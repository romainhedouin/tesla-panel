import socket

serverMACAddress = 'B8:27:EB:A5:89:A8'
port = 5
s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
s.connect((serverMACAddress, port))
while 1:
    text = input("Message: ")
    if text == "quit":
        break
    s.send(bytes(text, 'UTF-8'))
s.close()
