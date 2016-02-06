#!/usr/bin/env python3
import sys
import select
import time
import socket

host = '127.0.0.1'
port = 8081
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((host, port))
server.listen(16) # wtf is 16?


print("it works?")

def idle_work():
    # print("Doing idle work (well, pretending)")
    time.sleep(0.1) # don't want to tight loop

def generate_headers():
    return b"""HTTP/1.1 200 OK
Server: MyFirstWebserver/0.1
Content-Type: text/html; charset=UTF-8
Connection: close


"""

def dispatch_error(socket, method, headers):
    socket.send(b"HTTP/1.1 404 Not Found")

def dispatch_get(socket, method, headers):
    if b'favicon' in method:
        print("Rejecting request for a favicon")
        dispatch_error()
        return

    _, resource, *rest = method.split()

    print(resource)


def test(socket, headers):
    hvals = {}
    for h in headers:
        if b':' in h:
            h_name, h_data, *rest = h.split(b':')
            # print(h_name)
            hvals[h_name] = h_data
        elif len(h) != 0:
            print(h)

    # setup a real http response
    socket.send(generate_headers())
    socket.send(b"<h1>My First Webserver</h1>")
    socket.send(b"<ol>")
    for name, val in hvals.items():
        socket.send(b"<li>" + b' - '.join([name, val]) + b'</li>\n')
    socket.send(b"</ol>")


def handle_client_msg(socket, data):
    headers = data.split(b'\r\n')
    method = headers.pop(0)

    if method.startswith(b'GET'):
        dispatch_get(socket, method, headers)
    else:
        dispatch_error(socket, method, headers)

    socket.close()
    read_list.remove(socket)

read_list = [sys.stdin, server]

quit = False
timeout = 0  # seconds

while not quit:
    # check if there is anything on stdin
    ready = select.select(read_list, [], [], timeout)[0]
    if not ready:
        idle_work()  # do idle work here
    else:
        for file in ready:
            if file is server:
                client, address = server.accept()
                print("connection from ", address)
                read_list.append(client)
            elif file is sys.stdin:
                ch = sys.stdin.read(1)
                if ch == 'q':
                    quit = True
            else:
                # file must be a client
                data = file.recv(1024)
                if len(data) > 0:
                    # print("from client: ", data.decode('utf-8'))
                    handle_client_msg(file, data)
                else:
                    print("looks like we lost someone :(")
                    read_list.remove(file)

# Close anything that's left
for file in read_list:
    file.close()
