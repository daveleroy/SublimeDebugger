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


class Process:
	def __init__(self, command: List[str], on_stdout: Optional[Callable[[str], None]], on_stderr: Optional[Callable[[str], None]], on_close: Optional[Callable[[], None]] = None, cwd=None) -> None:
		print('Starting process: {}'.format(command))

		# taken from Default/exec.py
		# Hide the console window on Windows
		startupinfo = None
		if os.name == "nt":
			startupinfo = subprocess.STARTUPINFO() #type: ignore
			startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW #type: ignore

		self.process = subprocess.Popen(command, 
			stdout=subprocess.PIPE, 
			stderr=subprocess.PIPE, 
			stdin=subprocess.PIPE, 
			shell=False,
			bufsize=0,
			startupinfo=startupinfo,
			cwd = cwd)

		self.pid = self.process.pid
		self.on_stdout = on_stdout
		self.on_stderr = on_stderr
		self.on_close = on_close
		self.closed = False
		if on_stdout:
			thread = threading.Thread(target=self._read, args=(self.process.stdout, on_stdout))
			thread.start()

		if on_stderr:
			thread = threading.Thread(target=self._read, args=(self.process.stderr, on_stderr))
			thread.start()

	def _read(self, file: Any, callback: Callable[[str], None]) -> None:
		while not self.closed:
			self.process.poll()
			try:
				line = file.read(2**15).decode('UTF-8')
				if not line:
					core.log_info("Nothing to read from process, closing")
					break

				core.call_soon_threadsafe(callback, line)
			except Exception as err:
				core.log_exception()
				break

		self.close()

	def close(self) -> None:
		if self.closed:
			return
		if self.on_close:
			core.call_soon_threadsafe(self.on_close)
		self.closed = True

		try:
			# taken from the default/exec package
			if sys.platform == "win32":
				# terminate would not kill process opened by the shell cmd.exe,
				# it will only kill cmd.exe leaving the child running
				startupinfo = subprocess.STARTUPINFO()
				startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
				subprocess.Popen(
					"taskkill /PID %d /T /F" % self.pid,
					startupinfo=startupinfo)
			else:
				try:
					os.killpg(self.process.pid, signal.SIGTERM)
				except ProcessLookupError as e:
					pass

				self.process.terminate()
		except Exception as e:
			core.log_exception()
			
	def poll(self) -> Optional[int]:
		return self.process.poll()

	def dispose(self) -> None:
		try:
			self.close()
		except Exception as e:
			core.log_exception(e)


class Transport:
	def send(self, message: str) -> None:
		assert False

	def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
		assert False

	def dispose(self) -> None:
		assert False


CONTENT_HEADER = b"Content-Length: "

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
		if self.process == None:
			return
		self.process = None
		self.send_queue.put(None)  # kill the write thread as it's blocked on send_queue
		core.call_soon_threadsafe(self.on_closed)

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

				if content_length > 0:
					total_content = b""
					while (self.process and content_length > 0):
						content = self.process.stdout.read(content_length)
						content_length -= len(content)
						total_content += content

					if content_length == 0:
						message = total_content.decode("UTF-8")
						core.call_soon_threadsafe(self.on_receive, message)

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
					core.log_info('<< ', message)
				except (BrokenPipeError, OSError) as err:
					print("Failure writing to stdout", err)
					self.close()
