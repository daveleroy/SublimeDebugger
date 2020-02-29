'''
This code was modified from https://github.com/tomv564/LSP with the following license 

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

from ..typecheck import *

from queue import Queue
import socket
import threading
import time
import signal
import os
import subprocess
import sys

from .. import core

class Transport(Protocol):
	def write(self, message: str) -> None:
		...
	def readline(self) -> str:
		...
	def read(self, n: int) -> str:
		...
	def dispose(self) ->None:
		...


CONTENT_HEADER = "Content-Length: "

class TransportProtocol:
	def __init__(self, transport: Transport) -> None:
		self.transport = transport
		self.closed = False
		self.send_queue = Queue()  # type: Queue[Optional[str]]

	def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
		self.on_receive = on_receive
		self.on_closed = on_closed
		self.write_thread = threading.Thread(target=self.write_stdin)
		self.write_thread.start()
		self.read_thread = threading.Thread(target=self.read_stdout)
		self.read_thread.start()

	def close(self) -> None:
		print("closed transport protocol", self.closed)
		if self.closed:
			return
		self.closed = True
		self.transport.dispose()
		self.send_queue.put(None)  # kill the write thread as it's blocked on send_queue
		core.call_soon_threadsafe(self.on_closed)
		
		print("closed transport protocol")

	def dispose(self) -> None:
		self.close()

	def read_stdout(self) -> None:
		"""
		Reads JSON responses from process and dispatch them to response_handler
		"""
		while True:
			try:
				content_length = 0
				while True:
					header = self.transport.readline()
					if header:
						header = header.strip()
					if not header:
						break
					if header.startswith(CONTENT_HEADER):
						content_length = int(header[len(CONTENT_HEADER):])

				if content_length > 0:
					total_content = ""
					while (content_length > 0):
						content = self.transport.read(content_length)
						content_length -= len(content)
						total_content += content

					if content_length == 0:
						core.call_soon_threadsafe(self.on_receive, total_content)

			except (OSError, EOFError) as err:
				core.log_exception()
				break

		print("closing transport protocol")
		self.close()

	def send(self, message: str) -> None:
		self.send_queue.put(message)

	def write_stdin(self) -> None:
		while True:
			message = self.send_queue.get()
			if message is None:
				break
			try:
				self.transport.write(f'Content-Length: {len(message)}\r\n\r\n{message}')
				core.log_info('<< ', message)
			except (BrokenPipeError, OSError) as err:
				print("Failure writing to stdout", err)
				self.close()
