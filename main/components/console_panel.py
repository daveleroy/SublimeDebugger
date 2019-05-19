from sublime_db.core.typecheck import List, Callable, Optional

import os
import sublime
import re

from sublime_db import ui, core

from .variable_component import (
	Variable,
	VariableStateful,
	VariableStatefulComponent
)
from sublime_db.main.debug_adapter_client.types import Source, OutputEvent

from .layout import console_panel_width

ERROR = 1
OUTPUT = 1 << 1
TEXT = 1 << 2
NONE = 1 << 3
IGNORE = 1 << 4


class ConsoleItem (ui.Block):
	def __init__(self, on_navigate_to_source: Callable[[Source, int], None], kind: int, text: str, variable: Optional[Variable], source: Optional[Source] = None, line: Optional[int] = None):
		super().__init__()
		self.kind = kind
		self.text = text
		self.on_navigate_to_source = on_navigate_to_source
		if variable:
			self.variable = VariableStateful(variable, self.dirty)
		else:
			self.variable = None

		self.source = source
		self.line = line

	def render(self) -> ui.Block.Children:
		width = console_panel_width(self.layout) - 1
		source_item = None
		if self.source:
			width -= 15

			if self.line:
				source_text = "{}@{}".format(self.source.name, self.line)
			else:
				source_text = self.source.name

			if self.variable:
				text_width = width - self.layout.em_width() * (len(self.variable.name) + len(self.variable.value)) + 15 - 1.5
			else:
				text_width = 15

			source_item = ui.Button(self.on_clicked_source, [
				ui.Label(source_text, width=text_width, align=1, color='secondary')
			])

		if self.variable:
			return [VariableStatefulComponent(self.variable, itemRight=source_item)]

		items = []

		if self.kind == TEXT:
			items.append(ui.Label(self.text, width=width, align=0, color='secondary'))
		elif (self.kind == OUTPUT) or (self.kind == NONE):
			items.append(ui.Label(self.text, width=width, align=0, color='primary'))
		elif self.kind == ERROR:
			items.append(ui.Label(self.text, width=width, align=0, color='red'))
		elif self.kind == IGNORE:
			items.append(ui.Label(self.text, width=width, align=0, color='secondary'))
		else:
			assert None, "expected type..."


		if source_item:
			items.append(source_item)

		return [
			ui.block(*items)
		]

	def on_clicked_source(self):
		self.on_navigate_to_source(self.source, self.line or 0)

class ConsolePanel (ui.Block):
	class Filter:
		def __init__(self, name, enabled):
			self.name = name
			self.enabled = enabled

	def __init__(self, on_click: Callable[[], None], on_navigate_to_source: Callable[[Source, int], None]):
		super().__init__()
		self.items = [] #type: List[ui.Block]
		self.text = [] #type: List[str]
		self.on_click = on_click
		self.on_navigate_to_source = on_navigate_to_source
		self.filter = ERROR | OUTPUT | TEXT | NONE
		self.event_filter_map = {
			None: OUTPUT,
			"console": OUTPUT,
			"stderr": ERROR,
			"stdout": OUTPUT,
			"telemetry": IGNORE
		}
		self.filters = [
			ConsolePanel.Filter("output: debugger", True),
			ConsolePanel.Filter("output: program", True),
			ConsolePanel.Filter("output: other", True),
			ConsolePanel.Filter("output: telemetry", False)
		]
		self.updated_filter()

	def open_console_menu(self, selected_index=0):
		values = []
		class ListInputItemChecked (ui.ListInputItem):
			def __init__(self, name, checked):
				n = ""
				if checked: n += '● '
				else: n += '○ '
				n += name
				super().__init__(n, name)

		for filter in self.filters:
			values.append(ListInputItemChecked(filter.name, filter.enabled))

		input = ui.ListInput(values, placeholder="filter console output", index=selected_index)
		def run_command(list, **args):
			i = list
			self.filters[i].enabled = not self.filters[i].enabled
			self.updated_filter()
			self.open_console_menu(i)

		ui.run_input_command(input, run_command)

	def updated_filter(self):
		mask = 0
		if self.filters[0].enabled:
			mask |= TEXT
		if self.filters[1].enabled:
			mask |= ERROR | OUTPUT
		if self.filters[2].enabled:
			mask |= NONE
		if self.filters[3].enabled:
			mask |= IGNORE
		self.filter = mask
		self.dirty()

	def get_text(self) -> str:
		return ''.join(self.text)

	def open_in_view(self) -> None:
		file = sublime.active_window().new_file()
		file.run_command('append', {
                    'characters': self.get_text(),
                 			'scroll_to_end': True
		})

	def add(self, event: OutputEvent):
		filter = self.event_filter_map.get(event.category, NONE)
		source = event.source
		line = event.line
		text = event.text

		if (filter & (OUTPUT | ERROR)):
			match = re.match("(.*):([0-9]+):([0-9]+): error: (.*)", text)
			if match:
				source = Source(None, match.group(1), 0, 0, None, None)
				line = int(match.group(2))
				text = match.group(4)

		item = ConsoleItem(self.on_navigate_to_source, filter, text, None, source, line)
		self.items.append(item)
		self.dirty()

	def add_variable(self, variable: Variable, source: Optional[Source] = None, line: Optional[int] = None) -> None:
		self.text.append(variable.name)
		self.text.append(' = ')
		self.text.append(variable.value)

		item = ConsoleItem(self.on_navigate_to_source, OUTPUT, "", variable, source, line)
		self.items.append(item)
		self.dirty()

	def Add(self, text: str) -> None:
		self.text.append(text)
		for line in reversed(text.rstrip('\r\n').split('\n')):
			item = ConsoleItem(self.on_navigate_to_source, TEXT, line, None)
			self.items.append(item)
		self.dirty()

	def AddOutputOther(self, text: str) -> None:
		self.text.append(text)
		for line in reversed(text.rstrip('\r\n').split('\n')):
			item = ConsoleItem(self.on_navigate_to_source, NONE, line, None)
			self.items.append(item)
		self.dirty()

	def AddStdout(self, text: str) -> None:
		self.text.append(text)
		for line in reversed(text.rstrip('\r\n').split('\n')):
			item = ConsoleItem(self.on_navigate_to_source, OUTPUT, line, None)
			self.items.append(item)
		self.dirty()

	def AddStderr(self, text: str) -> None:
		self.text.append(text)
		for line in reversed(text.rstrip('\r\n').split('\n')):
			item = ConsoleItem(self.on_navigate_to_source, ERROR, line, None)
			self.items.append(item)
		self.dirty()

	def clear(self) -> None:
		self.items.clear()
		self.text.clear()
		self.dirty()

	def render(self) -> ui.Block.Children:
		count = int(self.layout.height() / 1.525) - 2.0
		items = []

		for item in reversed(self.items):
			if len(items) >= count:
				break
			if item.kind & self.filter:
				items.append(item)
		items.reverse()
		items.append(ui.Button(self.on_click, items=[
			ui.Img(ui.Images.shared.right),
		]))
		return [
			ui.Table(items=items)
		]
