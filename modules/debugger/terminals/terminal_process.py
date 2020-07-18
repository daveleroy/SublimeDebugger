from ...typecheck import *
from ...import core
from .import Terminal

import threading
import re

try:
	if core.platform.windows:
		from winpty import PtyProcess  #type: ignore
	else:
		from ...libs.ptyprocess import PtyProcess as _PtyProcess  #type: ignore

		class PtyProcess(_PtyProcess):  #type: ignore
			def read(self):
				return super().read().decode('utf-8')

	SUPPORTED = True

except ImportError:
	# this stuff is broken on > 4000 until the packages are 3.8 compatible
	SUPPORTED = False

# from https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')


class TtyProcess:
	def __init__(self, command: List[str], on_output: Optional[Callable[[str], None]], on_close: Optional[Callable[[], None]] = None, cwd=None) -> None:
		print('Starting process: {}'.format(command))

		self.process = PtyProcess.spawn(command, cwd=cwd)
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
					core.log_info("Nothing to read from process, closing")
					break

				#this isn't perfect we can easily miss some escapes since characters could span part of a single escape sequence...
				characters = ansi_escape.sub('', characters)
				core.call_soon_threadsafe(callback, characters)
			except EOFError as err:
				break
			except Exception as err:
				core.log_exception()
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
			core.log_exception(e)


class TerminalProcess (Terminal):
	def __init__(self, cwd: Optional[str], args: List[str]) -> None:
		cwd = cwd or None # turn "" into None

		super().__init__("Terminal", cwd=cwd)
		self.process = TtyProcess(args, on_output=self.on_process_output, cwd=cwd)

	def pid(self) -> int:
		return self.process.pid

	def on_process_output(self, output: str) -> None:
		self.add('stdout', output)

	def writeable(self) -> bool:
		return True

	def writeable_prompt(self) -> str:
		if self.escape_input:
			return "click to write escaped input to stdin"
		return "click to write a line to stdin"

	def write(self, text: str):
		if self.escape_input:
			text = text.encode('utf-8').decode("unicode_escape")

		self.process.write(text + '\n')

	def can_escape_input(self) -> bool:
		return True

	def dispose(self):
		self.process.dispose()
