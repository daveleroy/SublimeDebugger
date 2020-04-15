from ...typecheck import *
from ...import core
from ...dap import Transport

import socket
import os
import subprocess
import re
import threading
import sys
import signal

class Process(subprocess.Popen):
	def __init__(self, command: List[str], cwd: Optional[str]):
		# taken from Default/exec.py
		# Hide the console window on Windows
		startupinfo = None
		if os.name == "nt":
			startupinfo = subprocess.STARTUPINFO() #type: ignore
			startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW #type: ignore

		super().__init__(command, 
			stdout=subprocess.PIPE, 
			stderr=subprocess.PIPE, 
			stdin=subprocess.PIPE, 
			shell=False,
			bufsize=0,
			startupinfo=startupinfo,
			cwd = cwd)

		self.closed = False

	def dispose(self):
		self.closed = True
		try:
			self.terminate()
		except Exception as e:
			core.log_exception()


class StdioTransport(Transport):
	def __init__(self, log: core.Logger, command: List[str], cwd: Optional[str] = None):
		self.process = Process(command, cwd)

		thread = threading.Thread(target=self._read, args=(self.process.stderr, log.info))
		thread.start()

	def _read(self, file: Any, callback: Callable[[str], None]) -> None:
		while True:
			try:
				line = file.read(2**15).decode('UTF-8')
				if not line:
					core.log_info("Nothing to read from process, closing")
					break

				core.call_soon_threadsafe(callback, line)
			except Exception as e:
				core.log_exception()
				break

		self.process.dispose()

	def write(self, message: bytes) -> None:
		self.process.stdin.write(message)
		self.process.stdin.flush()

	def readline(self) -> bytes:
		if l := self.process.stdout.readline():
			return l
		raise EOFError

	def read(self, n: int) -> bytes:
		if l := self.process.stdout.read(n):
			return l
		raise EOFError

	def dispose(self) -> None:
		self.process.dispose()

class SocketTransport(Transport):
	def __init__(self, log: core.Logger, command: List[str], cwd: Optional[str] = None):

		self.process = Process(command, cwd)

		line = self.process.stdout.readline().decode('utf-8')
		result = re.match(r'Listening on port (.*)', line)
		if result:
			port = int(result.group(1))

		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect(('localhost', port))
		self.stdin = self.socket.makefile('wb')
		self.stdout = self.socket.makefile('rb')

		thread = threading.Thread(target=self._read, args=(self.process.stderr, log.info))
		thread.start()

	def _read(self, file: Any, callback: Callable[[str], None]) -> None:
		while True:
			try:
				line = file.read(2**15).decode('UTF-8')
				if not line:
					core.log_info("Nothing to read from process, closing")
					break
				core.log_info(line)
				core.call_soon_threadsafe(callback, line)
			except Exception as e:
				core.log_exception()
				break

	def write(self, message: bytes) -> None:
		self.stdin.write(message)
		self.stdin.flush()

	def readline(self) -> bytes:
		if l := self.stdout.readline():
			return l
		raise EOFError

	def read(self, n: int) -> bytes:
		if l := self.stdout.read(n):
			return l
		raise EOFError

	def dispose(self) -> None:
		self.process.dispose()
