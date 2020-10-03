from ...typecheck import *
from ...import core
from ...import ui

from ..terminals.terminal import Terminal, Line
from ..import dap

from .variable import VariableComponent

from . import css

from ..autocomplete import Autocomplete

import re
import webbrowser
import sublime

url_matching_regex = re.compile(r"((http|ftp|https)://([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?)") # from https://stackoverflow.com/questions/6038061/regular-expression-to-find-urls-within-a-string
default_file_regex = re.compile("(.*):([0-9]+):([0-9]+): error: (.*)")


_css_for_type = {
	"console": css.label,
	"stderr": css.label_redish,
	"stdout": css.label,

	"debugger.error": css.label_redish_secondary,
	"debugger.info": css.label_secondary,
	"debugger.output": css.label_secondary,

	"terminal.output": css.label_secondary,
	"terminal.error": css.label_redish,
}

class LineSourceView (ui.span):
	def __init__(self, name: str, line: Optional[int], text_width: int, on_clicked_source: Callable[[], None]):
		super().__init__()
		self.on_clicked_source = on_clicked_source
		self.name = name
		self.line = line
		self.text_width = text_width

	def render(self) -> ui.span.Children:
		if self.line:
			source_text = "{}@{}".format(self.name, self.line)
		else:
			source_text = self.name

		source_text = source_text.rjust(self.text_width)

		return [
			ui.click(self.on_clicked_source)[
				ui.text(source_text, css=css.label_secondary)
			]
		]


class LineView (ui.div):
	def __init__(self, line: Line, max_line_length: int, on_clicked_source: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__()
		self.line = line
		self.css = _css_for_type.get(line.type, css.label_secondary)
		self.max_line_length = max_line_length
		self.on_clicked_source = on_clicked_source
		self.clicked_menu = None

	def get(self) -> ui.div.Children:
		if self.line.variable:
			source = self.line.source
			component = VariableComponent(self.line.variable, source=self.line.source, on_clicked_source=self.on_clicked_source)
			return [component]

		span_lines = [] #type: List[ui.div]
		spans = [] #type: List[ui.span]
		max_line_length = self.max_line_length
		leftover_line_length = max_line_length

		# if we have a name/line put it to the right of the first line
		source = None
		if self.line.source:
			source = self.line.source.name

			# reserve at least the length of the label and a space before it to render the source button
			leftover_line_length -= len(source)
			leftover_line_length -= 1

		def add_source_if_needed():
			if not span_lines and source:
				def on_clicked_source():
					self.on_clicked_source(self.line.source)

				source_text = source.rjust(leftover_line_length + len(source) + 1)

				spans.append(ui.click(on_clicked_source)[
					ui.text(source_text, css=css.label_secondary)
				])

		span_offset = 0
		line_text = self.line.line
		while span_offset < len(line_text) and max_line_length > 0:
			if leftover_line_length <= 0:
				add_source_if_needed()
				span_lines.append(ui.div(height=css.row_height)[spans])
				spans = []
				leftover_line_length = max_line_length

			text = line_text[span_offset:span_offset + leftover_line_length]
			span_offset += len(text)
			spans.append(ui.click(lambda text=text: self.click(text))[
				ui.text(text, css=self.css)
			])
			leftover_line_length -= len(text)

		add_source_if_needed()
		span_lines.append(ui.div(height=css.row_height)[spans])

		if len(span_lines) == 1:
			return span_lines

		span_lines.reverse()
		return span_lines

	@core.schedule
	async def click(self, text: str):
		values = [
			ui.InputListItem(lambda: sublime.set_clipboard(text), "Copy"),
		]
		for match in url_matching_regex.findall(text):
			values.insert(0, ui.InputListItem(lambda match=match: webbrowser.open_new_tab(match[0]), "Open"))

		if self.line.source:
			values.insert(0, ui.InputListItem(lambda: self.on_clicked_source(self.line.source), "Navigate"))

		if self.clicked_menu:
			values[0].run()
			self.clicked_menu.cancel()
			return

		values[0].text += "\t Click again to select"

		self.clicked_menu = ui.InputList(values, text).run()
		await self.clicked_menu
		self.clicked_menu = None


class TerminalView (ui.div):
	def __init__(self, terminal: Terminal, on_clicked_source: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__(css=css.padding_left)
		self.terminal = terminal
		self.terminal.on_updated.add(self._on_updated_terminal)
		self.start_line = 0
		self.on_clicked_source = on_clicked_source

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

	def on_clear(self) -> None:
		self.terminal.clear()

	def render(self):
		assert self.layout
		lines = []
		height = 0
		max_height = int((self.layout.height() - css.header_height)/css.row_height) - 2.0
		count = len(self.terminal.lines)
		start = 0

		width = self.width(self.layout) - self.css.padding_width
		max_line_length = int(width)
		start = int(self.start_line)

		for line in self.terminal.lines[::-1][start:]:
			for l in LineView(line, max_line_length, self.on_clicked_source).get():
				height += 1
				if height > max_height:
					break
				lines.append(l)

		for line in self.terminal.lines[::-1][0:start][::-1]:
			for l in reversed(LineView(line, max_line_length, self.on_clicked_source).get()):
				height += 1
				if height > max_height:
					break
				lines.insert(0, l)


		lines.reverse()

		# if height > max_height:
		# 	self.start_line = min()

		if self.terminal.writeable():
			input_line = []
			if self.terminal.can_escape_input():
				if self.terminal.escape_input:
					text = 'esc'
				else:
					text = 'line'

				mode_toggle = ui.click(self.on_toggle_input_mode)[
					ui.text(text, css=css.button_secondary),
				]

				input_line.append(mode_toggle)

			label = self.terminal.writeable_prompt()
			input_line.append(
				ui.click(self.on_input)[
					ui.icon(ui.Images.shared.right),
					ui.text(label, css=css.label_secondary_padding),
				]
			)
			lines.append(ui.div(height=css.row_height)[input_line])

		return lines
