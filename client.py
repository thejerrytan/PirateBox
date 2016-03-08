import os
import sys
import socket
import time

######### GLOBAL VARIABLES ##########
MODE      = "SERVER" 	# 1 for server, 2 for client
HOST      = "localhost"
PORT      = 49000
SHAREDDIR = os.path.dirname(os.path.abspath(__file__))
CHUNK_SIZE = 1024

######### STATUS CODES ############
FILE_AVAILABLE   = 200
FILE_UNAVAILABLE = 404
SYNC_COMPLETE    = 100
REQUEST_FILE     = 111
NONE             = 000

###### ANSI COLOR CODES AND MESSAGE TYPE ######
class Ansi:
	HEADER    = '\033[95m'
	BLUE      = ('\033[94m', '[SYNC] ')
	GREEN     = ('\033[32m', '[COMMAND] ')
	YELLOW    = ('\033[33m', '[IO] ')
	FAIL      = ('\033[31m', '[LOG] ')
	ENDC      = '\033[0m'
	BOLD      = '\033[1m'
	UNDERLINE = '\033[4m'

def check_and_send_file(socket, relpath):
	abspath = os.path.join(SHAREDDIR, relpath)
	if os.path.exists(abspath) and os.path.isfile(abspath):
		response = "RES:%d\n" % FILE_AVAILABLE
		new_file = open(os.path.join(SHAREDDIR, relpath), 'rb')
		socket.sendall(response + new_file.read())
		print "[SEND] %s" % response
	else:
		response = "RES:%d\n" % FILE_UNAVAILABLE
		socket.sendall(response)
		print "[SEND] %s" % response

def request_and_get_file(socket, relpath):
	request = "REQ:%d\n%s" % (REQUEST_FILE, relpath)
	print "[SEND] %s" % request
	socket.sendall(request)
	while True:
		reply = socket.recv(1024)
		print "[RECV] %s" % reply
		status_code = get_status_code(reply)
		if status_code == FILE_AVAILABLE:
			new_file   = open(os.path.join(SHAREDDIR, relpath), 'wb')
			new_file.write(strip_header(reply)) 
			new_file.close()
			print_ansi(Ansi.YELLOW, "%s is written to disk at location %s" % (relpath, os.path.join(SHAREDDIR, relpath)))
			return True
		elif status_code == FILE_UNAVAILABLE:
			print_ansi(Ansi.BLUE, "%s is not available" % relpath)
			return False
		elif status_code == REQUEST_FILE:
			pass
		elif status_code == SYNC_COMPLETE:
			pass
		else:
			print_ansi(Ansi.FAIL, "Undefined message protocol.")
			pass

def send_directory_to_client(conn, dir_):
	s = ''
	for path in dir_:
		s += path + ','
	conn.sendall(s[:-1])

def send_directory_to_server(socket, dir_):
	s = ''
	for path in dir_:
		s += path + ','
	socket.sendall(s[:-1]) # remove last extra comma

def recv_directory(socket):	# must be connection for server side, socket for client side
	s = socket.recv(1024)
	return s.split(",")

def get_directory():
	dir_ = []
	for root, dirs, files in os.walk(SHAREDDIR):
		for file_ in files:
			dir_.append(os.path.relpath(os.path.join(root, file_), SHAREDDIR))
	return dir_

def sync_directory(socket, peer_dir):
	print "[SYNC] Beginning synchronization process"
	my_dir = get_directory()
	for file_ in peer_dir:
		if file_ not in my_dir:
			print_ansi(Ansi.BLUE, "%s is not present" % file_)
			time.sleep(5)
			request_and_get_file(socket, file_)
	sync_complete(socket)

def sync_complete(socket):
	request = "REQ:%d\n" % SYNC_COMPLETE
	socket.sendall(request)
	print "[SEND] %s" % request

def process_path(path):
	if path[0:2] == "./":
		# Relative paths
		return os.path.join(SHAREDDIR, path[2:])
	else:
		# Absolute paths
		return os.path.expanduser(path)

def get_status_code(header):
	if header is None or header == '':
		return NONE
	print_ansi(Ansi.FAIL, "get_status_code : " + repr(header.split(':')))
	(header, status_code) = header.split(':')
	return int(status_code[0:3])

def strip_header(msg):
	return msg[8:]

def prompt_user():
	print ">>>",
	return raw_input()
   
def print_ansi(color_type, msg):
	print color_type[0] + color_type[1] + msg + Ansi.ENDC

if __name__ == "__main__":
	socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	while True:
		print_ansi(Ansi.GREEN, "Specify your shared folder location:")
		SHAREDDIR = process_path(prompt_user())
		print_ansi(Ansi.GREEN, "Your shared folder is : %s" % SHAREDDIR)
		print_ansi(Ansi.GREEN, "Press 1 to accept incoming connection or 2 to connect")
		mode = prompt_user()
		if mode == '1':
			socket.bind((HOST,PORT))
			socket.listen(1)
			conn, addr = socket.accept()
			print_ansi(Ansi.GREEN, "Connected by: " + str(addr))
			server_dir = get_directory()
			client_dir = recv_directory(conn)
			send_directory_to_client(conn, server_dir)
			print_ansi(Ansi.BLUE, "Synchronizing files...do not disconnect")
			# socket.setblocking(0) # non-blocking mode now
			child_id = os.fork()
			if child_id != 0:
				# Parent process requests for files
				sync_directory(conn, client_dir)
				print_ansi(Ansi.BLUE, "Synchronization complete for you")
			else :
				# Child process service incoming requests
				done = False
				while not done:
					request = conn.recv(1024)
					print "[RECV] %s" % request
					status_code = get_status_code(request)
					if status_code == REQUEST_FILE:
						check_and_send_file(conn, strip_header(request))
					elif status_code == SYNC_COMPLETE:
						# Terminate child process
						print_ansi(Ansi.BLUE, "Synchronization complete for peer.")
						done = True
					else:
						print_ansi(Ansi.FAIL, "UNEXPECTED STATUS CODE")
				exit()
			# socket.setblocking(1)
			break
		elif mode == '2':
			print_ansi(Ansi.GREEN, "Enter a host to connect to:")
			HOST = prompt_user()
			print_ansi(Ansi.GREEN, "Connecting to host %s at PORT %s " % (HOST, PORT))
			try:
				socket.connect((HOST,PORT))
			except socket.socket.gaierror as e:
				print_ansi(Ansi.FAIL, "Error connecting to host. Please try again!")
			print_ansi(Ansi.GREEN, "Connection established!")
			print_ansi(Ansi.BLUE, "Synchronizing files...do not disconnect")
			client_dir = get_directory()
			send_directory_to_server(socket, client_dir)
			server_dir = recv_directory(socket)
			# socket.setblocking(1) # non-blocking mode now
			child_id = os.fork()
			if child_id != 0:
				# Parent process requests for files
				sync_directory(socket, server_dir)
				print_ansi(Ansi.BLUE, "Synchronization complete for you")
			else :
				# Child process service incoming requests
				csocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				
				done = False
				while not done:
					request = socket.recv(1024)
					print "[RECV] %s" % request
					status_code = get_status_code(request)
					if status_code == REQUEST_FILE:
						check_and_send_file(socket, strip_header(request))
					elif status_code == SYNC_COMPLETE:
						# Terminate child process
						print_ansi(Ansi.BLUE, "Synchronization complete for peer.")
						done = True
					else:
						print_ansi(Ansi.FAIL, "UNEXPECTED STATUS CODE")
				exit()
			# socket.setblocking(1)
			break
		elif mode == "exit":
			break
		else:
			print_ansi(Ansi.FAIL, "Invalid command: type exit to quit!")
	socket.close()