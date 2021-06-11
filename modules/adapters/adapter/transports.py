from __future__ import annotations
from ...typecheck import *

from ...import core
from ...dap import Transport

import socket
import os
import subprocess
import threading

class Process:
	@staticmethod
	async def check_output(command: list[str], cwd: str|None = None) -> bytes:
		return await core.run_in_executor(lambda: subprocess.check_output(command, cwd=cwd))

	def __init__(self, command: list[str], cwd: str|None = None):
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

		self.stdin = self.process.stdin
		self.stderr = self.process.stderr
		self.stdout = self.process.stdout

		self.closed = False

	def _readline(self, pipe) -> bytes:
		if l := pipe.readline():
			return l
		raise EOFError

	def _read(self, pipe, n: int) -> bytes:
		if l := pipe.read(n):
			return l
		raise EOFError

	async def readline(self, pipe) -> bytes:
		return await core.run_in_executor(lambda: self._readline(pipe))

	async def read(self, pipe, nbytes) -> bytes:
		return await core.run_in_executor(lambda: self._read(pipe, nbytes))

	def dispose(self):
		self.closed = True
		try:
			self.process.terminate()
		except Exception as e:
			core.log_exception()


class StdioTransport(Transport):
	def __init__(self, log: core.Logger, command: list[str], cwd: str|None = None, ignore_stderr: bool = False):
		log.log('transport', f'⟸ process/starting :: {command}')
		self.process = Process(command, cwd)


		if ignore_stderr:
			thread = threading.Thread(target=self._read, args=(self.process.stderr, print))
		else:
			thread = threading.Thread(target=self._read, args=(self.process.stderr, log.info))

		thread.start()

	def _read(self, file: Any, callback: Callable[[str], None]) -> None:
		while True:
			try:
				line = file.read(2**15).decode('UTF-8')
				if not line:
					core.log_info('Nothing to read from process, closing')
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
	def __init__(self, log: core.Logger, host: str, port: int, cwd: str|None = None):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect((host, port))
		self.stdin = self.socket.makefile('wb')
		self.stdout = self.socket.makefile('rb')

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
		try:
			self.socket.close()
		except:
			core.log_exception()
