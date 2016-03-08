import socket
import os
import shlex, subprocess

HOST = ""
PORT = 49000

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((HOST, PORT))
sock.listen(5)
conn, addr = sock.accept()

print "Connected by: " + str(addr)
while True:
	data = conn.recv(1024)
	print("RECV : " + data)
	conn.sendall(data)
	if data.lower() == "exit":
		break
	if not data: break
conn.close()