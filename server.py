#!/usr/bin/env python3
import sys
import select
import time
import socket

from collections import defaultdict

READ_LIST = []
WRITE_LIST = []
ERROR_LIST = []


# utility functions
def urldecode(data):
    data_s = data.decode('utf-8')
    data_s = data_s.replace('+', ' ')
    pairs = data_s.split('&')

    ret = {}

    for pair in pairs:
        bits = pair.split('=')
        key = bits.pop(0)
        if bits:
            value = bits.pop(0)
        else:
            value = None

        # could fully decode them here; remove %??'s and + and & encodings
        ret[key] = value

    return ret


class Client:

    def __init__(self, socket, address):
        self.socket = socket
        self.address = address

        self.resource_handlers = defaultdict(dict)

        self.send_buffer = []
        self.sending = None

        self.socket.setblocking(0)
        # print("Connection from: ", address)

        READ_LIST.append(self)

    def fileno(self):
        return self.socket.fileno()

    def close(self):
        self.socket.close()

    def shutdown(self):
        # print("Shutting down..")
        if self in READ_LIST:
            READ_LIST.remove(self)

        if self in WRITE_LIST:
            WRITE_LIST.remove(self)

        if self in ERROR_LIST:
            ERROR_LIST.remove(self)

        self.close()

    def queue(self, data):
        """Queue data to be sent on next send-select"""

        if self not in WRITE_LIST:
            WRITE_LIST.append(self)

        if not self.send_buffer:
            # add HTTP headers if we haven't done that yet
            self.send_buffer.append(self.generate_headers())

        # encode any string data as utf-8
        if isinstance(data, str):
            data = data.encode('utf-8')

        self.send_buffer.append(data)

    def handle_read(self):
        data = self.socket.recv(1024)
        if len(data) > 0:
            # print("from client: ", data.decode('utf-8'))
            self.handle_client_msg(data)
        else:
            # print("Disconnect from: {}".format(self.address))
            READ_LIST.remove(self)

    def handle_write(self):
        """Send any data waiting in either buffer"""

        if not self.send_buffer and not self.sending:
            return self.shutdown()

        if self.sending:
            # print("Continuing last send")
            self._send()
        else:
            self.sending = b''.join(self.send_buffer)
            self.send_buffer = []
            self._send()

    def _send(self):
        """Send queued data, but only up to SEND_SIZE at a time"""

        SEND_SIZE = 4096
        data = self.sending[:SEND_SIZE]
        sent = self.socket.send(data)
        # print("Sent {} bytes".format(sent))

        # adjust sending by the number of bytes sent
        self.sending = self.sending[sent:]
        # print("Remaining to send: {}".format(len(self.sending)))

        return sent

    def handle_client_msg(self, data):
        # headers end on first double newline
        header_end = data.index(b'\r\n\r\n')
        headers = data[:header_end].split(b'\r\n')

        payload = data[header_end + 4:]  # 4 for the double \r\n

        method = headers.pop(0)

        # print(method)
        if method.startswith(b'GET'):
            self.dispatch_get(self.socket, method, headers)
        elif method.startswith(b'POST'):
            self.dispatch_post(method, headers, payload)
        else:
            self.dispatch_error()

    def dispatch_error(self, *args):
        # print("404")
        self.send_buffer.append(b"HTTP/1.1 404 Not Found")
        self.send_buffer.append(b"404 Not Found")

        if self not in WRITE_LIST:
            WRITE_LIST.append(self)

    def dispatch_post(self, method, headers, payload):
        _, resource, *rest = method.split()
        resource = resource.decode('utf-8')

        print(resource)
        handler = self.resource_handlers['POST'].get(resource, self.dispatch_error)
        handler(method, resource, headers, payload)


    def dispatch_get(self, socket, method, headers):
        _, resource, *rest = method.split()
        resource = resource.decode('utf-8')

        print(resource)
        handler = self.resource_handlers['GET'].get(resource, self.dispatch_error)
        handler(method, resource, headers)



    def generate_headers(self):
        return b"""HTTP/1.1 200 OK
Server: MyFirstWebserver/0.2
Content-Type: text/html; charset=UTF-8
Connection: close


"""

    def register_resource(self, methods, path, callback):
        for method in methods:
            self.resource_handlers[method][path] = callback


class MyClient(Client):
    def __init__(self, *args):
        super(MyClient, self).__init__(*args)

        # register resources
        self.register_resource(['GET'], "/", self.index)
        self.register_resource(['POST'], "/myname", self.my_name)

        # setup other things
        self.count = 0

    def index(self, method, resource, headers):

        print("index called")
        self.queue("""
            <html>
                <head>
                <title>It works!</title>
                </head>
                <body>
                   <h1>My First Webserver</h1>
                   <p>Resource requested: {resource}</p>
                   <form method="POST" action="/myname">
                       <input type="text" name="name"/>
                       <button type="submit" name="submit">Submit</button>
                   </form>
                   <p>Total number of requests since server start: {count}</p>
                </body>
            </html>
        """.format(resource=resource, count=self.count))

    def my_name(self, method, resource, headers, payload=None):
        vals = urldecode(payload)

        self.queue("Hello there, {}!".format(vals['name']))

def idle_work():
    print("Doing idle work")
    time.sleep(0.1)  # pretend we did something


def event_loop(server, client_class):

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
                client = client_class(*server.accept())
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
    try:
        event_loop(server, MyClient)
    finally:
        print("Shutting down server...")
        # Close anything that's left
        for file in READ_LIST:
            file.close()

main()
