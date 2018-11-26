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

from sublime_db.core.typecheck import Optional, List, Any, Callable, Generator

from queue import Queue
import subprocess
import socket
import threading
import time

from sublime_db import core

class Process:
	def __init__(self, command: List[str], on_stdout: Optional[Callable[[str], None]], on_stderr: Optional[Callable[[str], None]]) -> None:
		print('Starting process: {}'.format(command))
		self.process = subprocess.Popen(command, stdout = subprocess.PIPE, stderr = subprocess.PIPE, stdin = subprocess.PIPE)
		self.on_stdout = on_stdout
		self.on_stderr = on_stderr

		if on_stdout:
			thread = threading.Thread(target=self._read, args= (self.process.stdout, on_stdout))
			thread.start()

		if on_stderr:
			thread = threading.Thread(target=self._read, args= (self.process.stderr, on_stderr))
			thread.start()

	def _read (self, file: Any, callback: Callable[[str], None]) -> None:
		while True:
			try:
				line = file.readline().decode('UTF-8')
				if not line:
					print("no data received, closing")
					break
				core.main_loop.call_soon_threadsafe(callback, line)
			except Exception as err:
				print("Failure reading from process", err)
				break
				
	def dispose(self) -> None:
		print('Ending process')
		try:
			self.process.kill()
		except OSError as e:
			print('OSError killing process: ', e)


class Transport:
	def send(self, message: str) -> None:
		assert False
	def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
		assert False
	def dispose(self) -> None:
		assert False

STATE_HEADERS = 0
STATE_CONTENT = 1
TCP_CONNECT_TIMEOUT = 5
CONTENT_HEADER = b"Content-Length: "

class TCPTransport(Transport):
	def __init__(self, s: socket.socket) -> None:
		self.socket = s  # type: 'Optional[socket.socket]'
		self.send_queue = Queue()  # type: Queue[Optional[str]]

	def start(self, on_receive: Callable[[str], None], on_closed: Callable[[], None]) -> None:
		self.on_receive = on_receive
		self.on_closed = on_closed
		self.read_thread = threading.Thread(target=self.read_socket)
		self.read_thread.start()
		self.write_thread = threading.Thread(target=self.write_socket)
		self.write_thread.start()

	def close(self) -> None:
		if self.socket == None: return
		self.send_queue.put(None)  # kill the write thread as it's blocked on send_queue
		self.socket = None
		core.main_loop.call_soon_threadsafe(self.on_closed)
		
	def dispose(self) -> None:
		self.close()

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
							if header.startswith(CONTENT_HEADER):
								header_value = header[len(CONTENT_HEADER):]
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

class StdioTransport(Transport):
	def __init__(self, process: Process) -> None:
		assert process.on_stdout == None, 'expected process to not read stdout'
		self.process = process.process  # type: Optional[subprocess.Popen]
		self.send_queue = Queue()  # type: Queue[Optional[str]]

	def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
		self.on_receive = on_receive
		self.on_closed = on_closed
		self.write_thread = threading.Thread(target=self.write_stdin)
		self.write_thread.start()
		self.read_thread = threading.Thread(target=self.read_stdout)
		self.read_thread.start()

	def close(self) -> None:
		if self.process == None: return
		self.process = None
		self.send_queue.put(None)  # kill the write thread as it's blocked on send_queue
		core.main_loop.call_soon_threadsafe(self.on_closed)

	def dispose(self) -> None:
		self.close()

	def read_stdout(self) -> None:
		"""
		Reads JSON responses from process and dispatch them to response_handler
		"""
		running = True
		while running and self.process:
			running = self.process.poll() is None

			try:
				content_length = 0
				while self.process:
					header = self.process.stdout.readline()
					if header:
						header = header.strip()
					if not header:
						break
					if header.startswith(CONTENT_HEADER):
						content_length = int(header[len(CONTENT_HEADER):])

				if (content_length > 0):
					content = self.process.stdout.read(content_length)
					message = content.decode("UTF-8")
					core.main_loop.call_soon_threadsafe(self.on_receive, message)

			except IOError as err:
				self.close()
				print("Failure reading stdout", err)
				break

		print("debug adapter process ended.")

	def send(self, message: str) -> None:
		self.send_queue.put(message)

	def write_stdin(self) -> None:
		while self.process:
			message = self.send_queue.get()
			if message is None:
				break
			else:
				try:
					self.process.stdin.write(bytes('Content-Length: {}\r\n\r\n'.format(len(message)), 'UTF-8'))
					self.process.stdin.write(bytes(message, 'UTF-8'))
					self.process.stdin.flush()
					print('<< ', message)
				except (BrokenPipeError, OSError) as err:
					print("Failure writing to stdout", err)
					self.close()