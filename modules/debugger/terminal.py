from .. typecheck import *
from .. import core, ui, dap
from .. commands import Autocomplete		

import os, threading, re
import sublime

class TtyProcess:
	def __init__(self, command: List[str], on_output: Optional[Callable[[str], None]], on_close: Optional[Callable[[], None]] = None, cwd=None) -> None:
		print('Starting process: {}'.format(command))

		if core.platform.windows:
			from winpty import PtyProcess
		else:
			from ptyprocess import PtyProcess

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
				line = self.process.read().decode('utf-8')
				if not line:
					core.log_info("Nothing to read from process, closing")
					break

				core.call_soon_threadsafe(callback, line)
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
		self.process.close(force=True)

	def dispose(self) -> None:
		try:
			self.close()
		except Exception as e:
			core.log_exception(e)

class Terminal:
	def __init__(self, name: str):
		self.lines = [] #type: List[Line]
		self.new_line = True
		self._name = name
		self.on_updated = core.Event()
		self.line_regex = re.compile("(.*):([0-9]+):([0-9]+): error: (.*)")
		self.escape_input = True

	def name(self) -> str:
		return self._name

	def clicked_source(self, source: dap.Source, line: Optional[int]) -> None:
		pass

	def _append(self, type: str, text: str, source: Optional[dap.Source] = None, source_line: Optional[int] = None):	
		lines = text.splitlines(keepends=True)
		for line in lines:
			if self.new_line or not self.lines or not isinstance(self.lines[-1], StandardLine):
				self.lines.append(StandardLine(type, self.clicked_source))
				self.new_line = False

			elif self.lines[-1].type != type:
				self.lines.append(StandardLine(type, self.clicked_source))
				self.new_line = False

			last = self.lines[-1]

			if source:
				last.source = source
				last.line = source_line

			last.append(line.rstrip('\r\n'))
			if line[-1] == '\n' or line[-1] == '\r':
				last.endline(self.line_regex)
				self.new_line = True
		self.on_updated.post()
	
	def clear(self) -> None:
		self.lines = []
		self.on_updated()

	def writeable(self) -> bool:
		return False
	def can_escape_input(self) -> bool:
		return False
	def writeable_prompt(self) -> str:
		return ""
	def write(self, text: str):
		assert False, "Panel doesn't support writing"

	def dispose(self):
		pass

class TerminalStandard(Terminal):
	def __init__(self, name: str) -> None:
		super().__init__(name)

	def write_stdout(self, text: str):
		self._append('stdout', text)

	def write_stderr(self, text: str):
		self._append('stderr', text)

class TerminalProcess (Terminal):
	def __init__(self, cwd: str, args: List[str]) -> None:
		super().__init__("Terminal")
		cwd = cwd or None # turn "" into None
		self.process = TtyProcess(args, on_output=self.on_process_output, cwd = cwd)

	def pid(self) -> int:
		return self.process.pid

	def on_process_output(self, output: str) -> None:
		self._append('stdout', output)

	def writeable(self) -> bool:
		return True
	
	def writeable_prompt(self) -> str:
		if self.escape_input:
			return "click to write a line to stdin"
		return "click to write escaped input to stdin"

	def write(self, text: str):
		if self.escape_input:
			text = text.encode('utf-8').decode("unicode_escape")

		self.process.write(text + '\n')
	
	def can_escape_input(self) -> bool:
		return True

	def dispose(self):
		self.process.dispose()


class Line:
	def ui(self, max_line_length) -> ui.Block:
		pass

_color_for_type = {
	"console": "primary",
	"stderr": "red",
	"stdout": "primary",

	"debugger.error": "red-secondary",
	"debugger.info": "secondary",
	"debugger.output": "secondary",
}

class LineSourceComponent (ui.Inline):
	def __init__(self, name: str, line: Optional[int], text_width: int, on_clicked_source):
		super().__init__()
		self.on_clicked_source = on_clicked_source
		self.name = name
		self.line = line
		self.text_width = text_width

	def render(self) -> ui.Inline.Children:
		if self.line:
			source_text = "{}@{}".format(self.name, self.line)
		else:
			source_text = self.name
		return [
			ui.Button(self.on_clicked_source, [
				ui.Label(source_text, width=self.text_width, align=1, color='secondary')
			])
		]

class StandardLine (Line):
	stdout = 0
	stderr = 1
	def __init__(self, type: str, on_clicked_source: Callable[[dap.Source, Optional[int]], None]) -> None:
		self.type = type
		self.text = ""
		self.source = None #type: Optional[dap.Source]
		self.line = None #type: Optional[int]
		self.color = _color_for_type.get(type, "secondary")
		self.on_clicked_source = on_clicked_source

	def append(self, text: str):
		self.text += text

	def endline(self, line_regex):
		if line_regex:
			match = line_regex.match(self.text)
			if match:
				source = dap.Source(None, match.group(1), 0, 0, None, None)
				line = int(match.group(2))
				self.text = match.group(4)
				self.source = source
				self.line = line

	

	def ui(self, layout, max_line_length) -> [ui.Block]:
		span_lines = []
		spans = []
		leftover_line_length = max_line_length
		
		# if we have a name/line put it to the right of the first line
		if self.source:
			leftover_line_length -= 15

		def add_name_and_line_if_needed(padding):
			if not span_lines and self.source:
				size = (padding + 15) * layout.em_width()
				def on_clicked_source():
					self.on_clicked_source(self.source, self.line)

				spans.append(LineSourceComponent(self.source.name, self.line, size, on_clicked_source))

		span_offset = 0
		while span_offset < len(self.text):
			if leftover_line_length <= 0:
				add_name_and_line_if_needed(0)
				span_lines.append(ui.block(*spans))
				spans = []
				leftover_line_length = max_line_length

			text = self.text[span_offset:span_offset + leftover_line_length]
			span_offset += len(text)
			spans.append(ui.Label(text, color=self.color))
			leftover_line_length -= len(text)


		add_name_and_line_if_needed(leftover_line_length)
		span_lines.append(ui.block(*spans))

		if len(span_lines) == 1:
			return span_lines

		span_lines.reverse()
		return span_lines
 

class TerminalComponent (ui.Block):
	def __init__(self, terminal: Terminal) -> None:
		super().__init__()
		self.terminal = terminal
		self.terminal.on_updated.add(self._on_updated_terminal)
		self.start_line = 0

	def _on_updated_terminal(self):
		self.dirty()

	def on_input(self):
		label = self.terminal.writeable_prompt()
		def run(value: str):
			if not value: return
			self.terminal.write(value)
			self.on_input()

		ui.InputText(run, label, enable_when_active=Autocomplete.for_window(sublime.active_window())).run()
	
	def on_toggle_input_mode(self):
		self.terminal.escape_input = not self.terminal.escape_input
		self.dirty()

	def action_buttons(self) -> List[Tuple[ui.Image, Callable]]:
		return [
			(ui.Images.shared.up, self.on_up),
			(ui.Images.shared.down, self.on_down),
			(ui.Images.shared.clear, self.on_clear),
		]

	def on_up(self) -> None:
		self.start_line += 10
		self.dirty()

	def on_down(self) -> None:
		self.start_line -= 10
		self.dirty()

	def on_clear(self) -> None:
		self.terminal.clear()

	def render(self):
		lines = []
		height = 0
		max_height = int(self.layout.height() / 1.525) - 2.0
		count = len(self.terminal.lines)
		start = 0
		from ..components.layout import console_panel_width

		width = console_panel_width(self.layout)
		max_line_length = int(width / self.layout.em_width())
		if count > max_height:
			start = self.start_line

		for line in self.terminal.lines[::-1][start:]:
			spans = line.ui(self.layout, max_line_length)
			lines.extend(spans)
			height += len(spans)

			if height >= max_height:
				break
		lines.reverse()

		if self.terminal.writeable():
			label = self.terminal.writeable_prompt()
			offset = (max_line_length - len(label)) * self.layout.em_width() - 2.0
			input = ui.Button(self.on_input, items=[
				ui.Img(ui.Images.shared.right),
				ui.Label(label, color="secondary"),
			])
			if self.terminal.can_escape_input():
				mode_toggle = ui.Button(self.on_toggle_input_mode, items = [
					ui.Label('\\esc', width=offset, align=1, color=["primary", "secondary"][self.terminal.escape_input]),
				])
				lines.append(ui.block(input, mode_toggle))
			else:
				lines.append(ui.block(input))
		
		return lines

