from debug.core.typecheck import Optional as Option, List, Any, Callable, Generator

import subprocess
import socket
import json
import sys
import threading
from time import sleep
from queue import Queue
import time

from debug import core

'''
This code was modified from here https://github.com/tomv564/LSP
'''

'''
MIT License

Copyright (c) 2017 Tom van Ommeren

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

class Process:
	def __init__(self, command: List[str], on_stdout: Callable[[str], None], on_stderr: Callable[[str], None]) -> None:
		print('Starting process: {}'.format(command))
		self.process = subprocess.Popen(command, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
		
		thread = threading.Thread(target=self._read, args= (self.process.stdout, on_stdout))
		thread.start()

		thread = threading.Thread(target=self._read, args= (self.process.stderr, on_stderr))
		thread.start()

	def _read (self, file: Any, callback: Callable[[str], None]) -> None:
		while True:
			try:
				line = file.readline().decode('ascii')
				if not line:
					print("no data received, closing")
					break
				core.main_loop.call_soon_threadsafe(callback, line)
			except Exception as err:
				print("Failure reading from process", err)
				break
				
	def dispose(self) -> None:
		print('Ending process')
		self.process.kill()

class Transport:
	def send(self, message: str) -> None:
		pass
	def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
		pass
	def dispose(self) -> None:
		pass

STATE_HEADERS = 0
STATE_CONTENT = 1
ContentLengthHeader = b"Content-Length: "
TCP_CONNECT_TIMEOUT = 5


class TCPTransport(Transport):
    def __init__(self, socket: 'Any') -> None:
        self.socket = socket  # type: 'Option[Any]'
        self.send_queue = Queue()  # type: Queue[Option[str]]

    def start(self, on_receive: Callable[[str], None], on_closed: Callable[[], None]) -> None:
        self.on_receive = on_receive
        self.on_closed = on_closed
        self.read_thread = threading.Thread(target=self.read_socket)
        self.read_thread.start()
        self.write_thread = threading.Thread(target=self.write_socket)
        self.write_thread.start()

    def close(self) -> None:
        self.send_queue.put(None)  # kill the write thread as it's blocked on send_queue
        self.socket = None
        core.main_loop.call_soon_threadsafe(self.on_closed)

    def read_socket(self) -> None:
        remaining_data = b""
        is_incomplete = False
        read_state = STATE_HEADERS
        content_length = 0
        while self.socket:
            is_incomplete = False
            try:
                received_data = self.socket.recv(4096)
            except Exception as err:
                print("Failure reading from socket", err)
                self.close()
                break

            if not received_data:
                print("no data received, closing")
                self.close()
                break

            data = remaining_data + received_data
            remaining_data = b""
            while len(data) > 0 and not is_incomplete:
                if read_state == STATE_HEADERS:
                    headers, _sep, rest = data.partition(b"\r\n\r\n")
                    if len(_sep) < 1:
                        is_incomplete = True
                        remaining_data = data
                    else:
                        for header in headers.split(b"\r\n"):
                            if header.startswith(ContentLengthHeader):
                                header_value = header[len(ContentLengthHeader):]
                                content_length = int(header_value)
                                read_state = STATE_CONTENT
                        data = rest

                if read_state == STATE_CONTENT:
                    # read content bytes
                    if len(data) >= content_length:
                        content = data[:content_length]
                        message = content.decode("UTF-8")
                        core.main_loop.call_soon_threadsafe(self.on_receive, message)
                        data = data[content_length:]
                        read_state = STATE_HEADERS
                    else:
                        is_incomplete = True
                        remaining_data = data

    def send(self, message: str) -> None:
        self.send_queue.put(message)

    def write_socket(self) -> None:
        while self.socket:
            message = self.send_queue.get()
            if message is None:
                break
            else:
                try:
                    self.socket.sendall(bytes('Content-Length: {}\r\n\r\n'.format(len(message)), 'UTF-8'))
                    self.socket.sendall(bytes(message, 'UTF-8'))
                    print(' << ', message)
                except Exception as err:
                    print("Failure writing to socket", err)
                    self.close()



# starts the tcp connection in a none blocking fashion
@core.async
def start_tcp_transport(host: str, port: int) -> core.awaitable[TCPTransport]:
	def start_tcp_transport_inner() -> TCPTransport:
		print('connecting to {}:{}'.format(host, port))
		start_time = time.time()
		while time.time() - start_time < TCP_CONNECT_TIMEOUT:
			try:
				sock = socket.create_connection((host, port))
				transport = TCPTransport(sock)
				return transport
			except ConnectionRefusedError as e:
				pass
		raise Exception("Timeout connecting to socket")

	print('connecting to {}:{}'.format(host, port))
	transport = yield from core.main_loop.run_in_executor(core.main_executor, start_tcp_transport_inner)
	return transport
