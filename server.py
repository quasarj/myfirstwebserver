#!/usr/bin/env python3
import sys
import select
import time
import socket

READ_LIST = []
WRITE_LIST = []
ERROR_LIST = []


class Client:

    def __init__(self, socket, address):
        self.socket = socket
        self.address = address

        self.send_buffer = []
        self.sending = None

        self.socket.setblocking(0)
        print("Connection from: ", address)

        READ_LIST.append(self)

    def fileno(self):
        return self.socket.fileno()

    def close(self):
        self.socket.close()

    def shutdown(self):
        print("Shutting down..")
        if self in READ_LIST:
            READ_LIST.remove(self)

        if self in WRITE_LIST:
            WRITE_LIST.remove(self)

        if self in ERROR_LIST:
            ERROR_LIST.remove(self)

        self.close()

    def queue(self, data):
        if self not in WRITE_LIST:
            WRITE_LIST.append(self)
        self.send_buffer.append(data)

    def handle_read(self):
        data = self.socket.recv(1024)
        if len(data) > 0:
            # print("from client: ", data.decode('utf-8'))
            self.handle_client_msg(data)
        else:
            print("Disconnect from: {}".format(self.address))
            READ_LIST.remove(self)

    def handle_write(self):
        if not self.send_buffer and not self.sending:
            return self.shutdown()

        if self.sending:
            print("Continuing last send")
            self._send()
        else:
            self.sending = b''.join(self.send_buffer)
            self.send_buffer = []
            self._send()

    def _send(self):
        SEND_SIZE = 10
        data = self.sending[:SEND_SIZE]
        sent = self.socket.send(data)
        print("Sent {} bytes".format(sent))

        # adjust sending by the number of bytes sent
        self.sending = self.sending[sent:]
        print("Remaining to send: {}".format(len(self.sending)))

        return sent


    def handle_client_msg(self, data):
        headers = data.split(b'\r\n')
        method = headers.pop(0)

        if method.startswith(b'GET'):
            self.dispatch_get(self.socket, method, headers)
        else:
            self.dispatch_error(self.socket, method, headers)

        # print("Closing socket")
        # self.close()
        # READ_LIST.remove(self)

    def dispatch_error(self, socket, method, headers):
        self.queue(b"HTTP/1.1 404 Not Found")

    def dispatch_get(self, socket, method, headers):
        if b'favicon' in method:
            print("Rejecting request for a favicon")
            dispatch_error(socket, method, headers)
            return

        _, resource, *rest = method.split()

        print(resource)
        self.queue(self.generate_headers())
        self.queue(b"<h1>My First Webserver</h1>")
        self.queue(b"<p>Resource requested: ")
        self.queue(resource)
        self.queue(b"</p>")

    def generate_headers(self):
        return b"""HTTP/1.1 200 OK
Server: MyFirstWebserver/0.2
Content-Type: text/html; charset=UTF-8
Connection: close


"""


def idle_work():
    print("Doing idle work")
    time.sleep(0.1)  # pretend we did something


def event_loop(server):
    quit = False
    timeout = 10  # seconds

    while not quit:
        # check if there is any i/o
        ready_read, ready_write, ready_error = \
            select.select(READ_LIST, WRITE_LIST, ERROR_LIST, timeout)

        if not ready_read and not ready_write and not ready_error:
            idle_work()  # do idle work here
            continue

        for file in ready_read:
            if file is server:
                client = Client(*server.accept())
            elif file is sys.stdin:
                ch = sys.stdin.read(1)
                if ch == 'q':
                    quit = True
            else:
                file.handle_read()

        for client in ready_write:
            client.handle_write()


def main():
    # setup server
    host = '0.0.0.0'  # bind to everything
    port = 8081
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # what does this do?
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setblocking(0)  # put in non-blocking mode
    server.bind((host, port))
    server.listen(16)  # wtf is 16?
    print("Listening")

    READ_LIST.extend([sys.stdin, server])
    event_loop(server)

    # Close anything that's left
    for file in READ_LIST:
        file.close()

main()
