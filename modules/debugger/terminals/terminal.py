from ...typecheck import*
from ...import (
	core,
	dap,
	ui,
)
from ..views import css
from ..variables import VariableComponent, Variable
from ..autocomplete import Autocomplete

import re
import webbrowser
import sublime

Source = Tuple[dap.Source, Optional[int]]

url_matching_regex = re.compile(r"((http|ftp|https)://([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?)") # from https://stackoverflow.com/questions/6038061/regular-expression-to-find-urls-within-a-string
default_line_regex = re.compile("(.*):([0-9]+):([0-9]+): error: (.*)")


class Line:
	def __init__(self, type: Optional[str]):
		self.type = type
		self.line = ''
		self.source = None #type: Optional[Source]
		self.variable = None #type: Optional[Variable]
		self.finished = False

	def add(self, text: str, source: Optional[Source], line_regex):
		if self.finished:
			raise core.Error('line is already complete')

		self.source = self.source or source
		self.line += text.rstrip('\r\n')
		if text[-1] == '\n' or text[-1] == '\r':
			self.finished = True
			if not self.source and line_regex:
				match = line_regex.match(self.line)
				if match:
					source = (dap.Source(None, match.group(1), 0, 0, None, []), int(match.group(2)))
					line = int(match.group(2))
					self.line = match.group(4)
					self.source = source

	def add_variable(self, variable: Variable, source: Optional[Source]):
		if self.finished:
			raise core.Error('line is already complete')

		self.finished = True
		self.variable = variable
		self.source = source

class Terminal:
	def __init__(self, name: str):
		self.lines = [] #type: List[Line]
		self._name = name
		self.on_updated = core.Event() #type: core.Event[None]
		self.line_regex = default_line_regex

		self.new_line = True
		self.escape_input = True

	def name(self) -> str:
		return self._name

	def clicked_source(self, source: dap.Source, line: Optional[int]) -> None:
		pass

	def _add_line(self, type: str, text: str, source: Optional[Source] = None):
		if self.lines:
			previous = self.lines[-1]
			if not previous.finished and previous.type == type:
				previous.add(text, source, self.line_regex)
				return
		
		line = Line(type)
		line.add(text, source, self.line_regex)
		self.lines.append(line)
		self.on_updated.post()

	def add(self, type: str, text: str, source: Optional[Source] = None):
		lines = text.splitlines(keepends=True)
		for line in lines:
			self._add_line(type, line, source)

	def add_variable(self, variable, source: Optional[Source] = None):
		line = Line(None)
		line.add_variable(variable, source)
		self.lines.append(line)
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



_css_for_type = {
	"console": css.label,
	"stderr": css.label_redish,
	"stdout": css.label,

	"debugger.error": css.label_redish_secondary,
	"debugger.info": css.label_secondary,
	"debugger.output": css.label_secondary,
}


class LineSourceView (ui.span):
	def __init__(self, name: str, line: Optional[int], text_width: int, on_clicked_source):
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
		return [
			ui.click(self.on_clicked_source)[
				ui.text(source_text, css=css.label_secondary_padding)
			]
		]


class LineView (ui.div):
	def __init__(self, line: Line, max_line_length: int, on_clicked_source: Callable[[dap.Source, Optional[int]], None]) -> None:
		super().__init__()
		self.line = line
		self.css = _css_for_type.get(line.type, css.label_secondary)
		self.max_line_length = max_line_length
		self.on_clicked_source = on_clicked_source
		self.clicked_menu = None

	def get(self) -> ui.div.Children:
		if self.line.variable:
			source = self.line.source
			source_item = None
			if source:
				def on_clicked_source():
					self.on_clicked_source(source[0], source[1])
				source_item = LineSourceView(source[0].name or '??', source[1], 15, on_clicked_source)

			component = VariableComponent(self.line.variable, item_right=source_item)
			return [component]



		span_lines = [] #type: List[ui.div]
		spans = [] #type: List[ui.span]
		max_line_length = self.max_line_length
		leftover_line_length = max_line_length

		# if we have a name/line put it to the right of the first line
		if self.line.source:
			leftover_line_length -= 15

		def add_name_and_line_if_needed(padding):
			source = self.line.source
			if not span_lines and source:
				def on_clicked_source():
					self.on_clicked_source(source[0], source[1])

				spans.append(LineSourceView(source[0].name or '??', source[1], 15, on_clicked_source))


		span_offset = 0
		line_text = self.line.line
		while span_offset < len(line_text):
			if leftover_line_length <= 0:
				add_name_and_line_if_needed(0)
				span_lines.append(ui.div(height=css.row_height)[spans])
				spans = []
				leftover_line_length = max_line_length

			text = line_text[span_offset:span_offset + leftover_line_length]
			span_offset += len(text)
			spans.append(ui.click(lambda: self.click(text))[
				ui.text(text, css=self.css)
			])
			leftover_line_length -= len(text)

		add_name_and_line_if_needed(leftover_line_length)
		span_lines.append(ui.div(height=css.row_height)[spans])

		if len(span_lines) == 1:
			return span_lines

		span_lines.reverse()
		return span_lines

	@core.schedule
	async def click(self, text: str):
		def copy():
			sublime.set_clipboard(text)

		values = [
			ui.InputListItem(copy, "Copy"),
		]

		for match in url_matching_regex.findall(text):
			values.insert(0, ui.InputListItem(lambda: webbrowser.open_new_tab(match[0]), "Open"))

		if self.clicked_menu:
			values[0].run()
			self.clicked_menu.cancel()
			return

		self.clicked_menu = ui.InputList(values, text).run()
		await self.clicked_menu
		self.clicked_menu = None

class TerminalView (ui.div):
	def __init__(self, terminal: Terminal, on_clicked_source: Callable[[dap.Source, Optional[int]], None]) -> None:
		super().__init__()
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
		assert self.layout
		lines = []
		height = 0
		max_height = int((self.layout.height() - css.header_height)/css.row_height) - 1.0
		count = len(self.terminal.lines)
		start = 0
		from ..views.layout import console_panel_width

		width = self.width(self.layout)
		max_line_length = int(width)
		if count > max_height:
			start = self.start_line

		for line in self.terminal.lines[::-1][start:]:
			for l in LineView(line, max_line_length, self.on_clicked_source).get():
				height += 1
				lines.append(l)
				if height >= max_height:
					break

			if height >= max_height:
					break
	
		lines.reverse()

		if self.terminal.writeable():
			input_line = []
			if self.terminal.can_escape_input():
				if self.terminal.escape_input:
					text = 'esc'
				else:
					text = 'line'

				mode_toggle = ui.span(css=css.button)[ui.click(self.on_toggle_input_mode)[
					ui.text(text, css=css.label_secondary),
				]]

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
