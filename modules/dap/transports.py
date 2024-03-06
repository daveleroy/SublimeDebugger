from __future__ import annotations
from dataclasses import dataclass
from io import BufferedReader, BufferedWriter
from typing import IO, Any, Callable

from ..import core
from .transport import Transport, TransportListener, TransportOutputLog, TransportConnectionError, TransportStream

import socket
import os
import subprocess
import threading

class Process:
	processes: set[subprocess.Popen] = set()

	@staticmethod
	def cleanup_processes():
		for self in Process.processes:
			if self.poll() is not None:
				core.info('killing process')
				self.kill()

		Process.processes.clear()

	@staticmethod
	def remove_finished_processes():
		finished = []
		for self in Process.processes:
			if self.poll() is not None:
				finished.append(self)

		for f in finished:
			Process.processes.remove(f)

	@staticmethod
	def add_subprocess(process: subprocess.Popen):
		Process.remove_finished_processes()
		Process.processes.add(process)

	@staticmethod
	@core.run_in_executor
	def check_output(command: list[str], cwd: str|None = None) -> bytes:
		return subprocess.check_output(command, cwd=cwd)

	def __init__(self, command: list[str]|str, cwd: str|None = None, env: dict[str, str]|None = None, shell = False):
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
			shell=shell,
			bufsize=0,
			startupinfo=startupinfo,
			cwd = cwd,
			env=env)

		Process.add_subprocess(self.process)

		stdin = self.process.stdin
		stderr = self.process.stderr
		stdout = self.process.stdout
		assert stdin and stderr and stdout

		self.stdin = stdin
		self.stderr = stderr
		self.stdout = stdout
		self.pid = self.process.pid
		self.closed = False

		self.on_closed: Callable[[], None]|None = None

	def on_stdout(self, callback: Callable[[str], None], closed: Callable[[], None]|None = None):
		thread = threading.Thread(target=self._read_all, args=(self.process.stdout, callback, closed), name='stdout')
		thread.start()

	def on_stderr(self, callback: Callable[[str], None], closed: Callable[[], None]|None = None):
		thread = threading.Thread(target=self._read_all, args=(self.process.stderr, callback, closed), name='stderr')
		thread.start()

	def _read_all(self, file: Any, callback: Callable[[str], None], closed: Callable[[], None]|None) -> None:
		while True:
			line = file.read(2**15).decode('UTF-8')
			if not line:
				break

			core.call_soon(callback, line)

		if closed:
			closed()

	def _readline(self, pipe: IO[bytes]) -> bytes:
		if l := pipe.readline():
			return l
		raise EOFError

	def _read(self, pipe: IO[bytes], n: int) -> bytes:
		if l := pipe.read(n):
			return l
		raise EOFError

	@core.run_in_executor
	def readline(self, pipe: IO[bytes]) -> bytes:
		return self._readline(pipe)

	@core.run_in_executor
	def read(self, pipe: IO[bytes], nbytes: int) -> bytes:
		return self._read(pipe, nbytes)

	def dispose(self):
		self.closed = True
		try:
			self.process.kill()
			self.process.wait()
		except Exception:
			core.exception()


@dataclass
class StdioTransport(TransportStream):
	command: list[str]
	cwd: str|None = None
	stderr: Callable[[str], None] | None = None
	process: Process|None = None

	async def setup(self):
		self.log('transport', f'-- stdio transport: {self.command}')
		self.process = Process(self.command, self.cwd or self.configuration.variables.get('folder'))
		self.process.on_stderr(self._log_stderr)

	def _log_stderr(self, data: str):
		self.log('transport', TransportOutputLog('stderr', data))
		if stderr := self.stderr:
			stderr(data)

	def write(self, message: bytes) -> None:
		assert self.process
		self.process.stdin.write(message)
		self.process.stdin.flush()

	def readline(self) -> bytes:
		assert self.process
		if l := self.process.stdout.readline():
			return l
		raise EOFError

	def read(self, n: int) -> bytes:
		assert self.process
		if l := self.process.stdout.read(n):
			return l
		raise EOFError

	def dispose(self) -> None:
		if self.process:
			self.process.dispose()


@dataclass
class SocketTransport(TransportStream):

	host: str = 'localhost'
	port: int = 0
	timeout: int = 5

	command: list[str]|None = None
	cwd: str|None = None
	env: dict[str, str]|None = None

	stderr: Callable[[str], None] | None = None
	stdout: Callable[[str], None] | None = None

	process: Process|None = None

	socket_stdin: BufferedWriter|None = None
	socket_stdout: BufferedReader|None = None

	async def setup(self):
		if self.command:
			self.log('transport', f'-- socket transport process: {self.command}')
			self.process = Process(self.command, cwd=self.cwd or self.configuration.variables.get('folder'), env=self.env)

		self.log('transport', f'-- socket transport: {self.host}:{self.port}')

		exception: Exception|None = None
		for _ in range(0, self.timeout * 4):
			try:
				self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self.socket.connect((self.host, self.port))
				exception = None
				self.log('transport', f'-- socket transport: {self.host}:{self.port}')
				break

			except Exception as e:
				try:
					self.socket.close()
				except:
					core.exception()

				await core.delay(0.25)
				exception = e

		if exception:
			raise TransportConnectionError(f'tcp://{self.host}:{self.port} {exception}')


		if self.process:
			self.process.on_stdout(self.stdout or (lambda data: self.log('transport', TransportOutputLog('stdout', data))))
			self.process.on_stderr(self.stderr or (lambda data: self.log('transport', TransportOutputLog('stderr', data))))

		self.socket_stdin = self.socket.makefile('wb')
		self.socket_stdout = self.socket.makefile('rb')


	def write(self, message: bytes) -> None:
		assert self.socket_stdin
		self.socket_stdin.write(message)
		self.socket_stdin.flush()

	def readline(self) -> bytes:
		assert self.socket_stdout
		if l := self.socket_stdout.readline():
			return l
		raise EOFError

	def read(self, n: int) -> bytes:
		assert self.socket_stdout
		if l := self.socket_stdout.read(n):
			return l
		raise EOFError

	def dispose(self) -> None:
		try:
			self.socket.close()
		except:
			core.exception()

		if self.process:
			self.process.dispose()
