from sublime_db.core.typecheck import List, Callable

import os
import sublime

from sublime_db import ui, core

from .variable_component import (VariableComponent, 
	Variable, 
	VariableState, 
	VariableComponent
)

class ConsolePanel (ui.Component):
	def __init__(self, on_click: Callable[[], None]):
		super().__init__()
		self.items = [] #type: List[ui.Component]
		self.text = [] #type: List[str]
		self.on_click = on_click

	def get_text (self) -> str:
		return ''.join(self.text)

	def open_in_view(self) -> None:
		file = sublime.active_window().new_file()
		file.run_command('append', {
			'characters' : self.get_text(),
			'scroll_to_end' : True
		})

	def AddVariable(self, variable: Variable) -> None:
		self.text.append(variable.name)
		self.text.append(' = ')
		self.text.append(variable.value)

		item = ConsoleVariable(variable)
		self.items.append(item)
		self.dirty()

	def Add(self, text: str) -> None:
		self.text.append(text)
		for line in reversed(text.rstrip('\n').split('\n')):
			item = ui.Label(line, color = 'secondary')
			self.items.append(item)
		self.dirty()

	def AddStdout(self, text: str) -> None:
		self.text.append(text)
		for line in reversed(text.rstrip('\n').split('\n')):
			item = ui.Label(line, color = 'primary')
			self.items.append(item)
		self.dirty()

	def AddStderr(self, text: str) -> None:
		self.text.append(text)
		for line in reversed(text.rstrip('\n').split('\n')):
			item = ui.Label(line, color = 'red')
			self.items.append(item)
		self.dirty()

	def clear(self) -> None:
		self.items.clear()
		self.text.clear()
		self.dirty()

	def render (self) -> ui.components:
		items = list(reversed(self.items[-25:]))
		return [
			ui.HorizontalSpacer(300),
			ui.Panel(items = [
				ui.Segment(items = [
					ui.Button(self.on_click, [
						ui.Label('Console')
					])
				]),
				ui.Table(items = items)
			])
		]

class ConsoleVariable (ui.Component):
	def __init__(self, variable: Variable) -> None:
		super().__init__()
		self.variable = VariableState(variable, self.dirty)
		self.variable.toggle_expand()

	def render(self) -> ui.components:
		items = []
		for v in self.variable.variables:
			# we replace the name with the value... since the name is a number
			# this seems to be what vscode does
			v.name = v.value
			v.value = ''
			items.append(VariableComponent(v))
		return items
