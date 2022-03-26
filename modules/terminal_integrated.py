from __future__ import annotations
from .typecheck import *

from .console_view import ConsoleView
from .typecheck import *

from .import core

import threading
import re

import sublime

class TerminalIntegrated:
	def __init__(self, window: sublime.Window, name: str, command: list[str], cwd: str|None):
		cwd = cwd or None # turn "" into None or PtyProcess will lockup?
		self.process = TtyProcess(command, on_output=self.on_process_output, cwd=cwd, on_close=self.on_process_closed)
		self.panel = ConsoleView(window, 'Terminal', self.on_output_closed)
		self.closed = False

	def dispose(self):
		self.panel.dispose()

	def pid(self):
		return self.process.pid

	def on_output_closed(self):
		...
		# self.process.close()

	def on_process_closed(self):
		self.closed = True

	def on_process_output(self, output: str):
		self.panel.write(output)



PTYPROCESS_SUPPORTED: bool = False

if core.platform.windows:
	...
	# if core.platform.is_64:
	# 	from .libs.pywinpty.st3_windows_x64.winpty import PtyProcess
	# else:
	# 	from .libs.pywinpty.st3_windows_x32.winpty import PtyProcess

else:
	from .libs.ptyprocess import PtyProcess as _PtyProcess  #type: ignore

	class PtyProcess(_PtyProcess):  #type: ignore
		def read(self) -> str:
			return super().read().decode('utf-8')

	PTYPROCESS_SUPPORTED = True


# from https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')

class TtyProcess:
	def __init__(self, command: list[str], on_output: Optional[Callable[[str], None]], on_close: Optional[Callable[[], None]] = None, cwd=None) -> None:
		print('Starting process: {}'.format(command))
		if not PTYPROCESS_SUPPORTED:
			raise core.Error("Unable to start external terminal PtyProcess is not supported on Windows at the moment (try using console instead of integrated terminal in your configuration)")

		self.process: Any = PtyProcess.spawn(command, cwd=cwd)
		self.pid = self.process.pid
		self.on_close = on_close
		self.closed = False
		if on_output:
			thread = threading.Thread(target=self._read, args=(on_output,))
			thread.start()

	def _read(self, callback: Callable[[str], None]) -> None:
		while not self.closed:
			try:
				characters = self.process.read()
				if not characters:
					core.info("Nothing to read from process, closing")
					break

				#this isn't perfect we can easily miss some escapes since characters could span part of a single escape sequence...
				characters = ansi_escape.sub('', characters)
				core.call_soon_threadsafe(callback, characters)
			except EOFError as err:
				break
			except Exception as err:
				core.exception()
				break

		self.close()

	def write(self, text: str):
		self.process.write(bytes(text, 'utf-8'))

	def close(self) -> None:
		if self.closed:
			return
		if self.on_close:
			core.call_soon_threadsafe(self.on_close)
		self.closed = True
		self.process.close(force=True,)

	def dispose(self) -> None:
		try:
			self.close()
		except Exception as e:
			core.exception(e)
