
import os
from sublime_db import ui, core

from sublime_db.core.typecheck import List

from sublime_db.main.components.variable_component import VariableComponent, Variable, VariableComponent

class EventLogVariable (ui.Component):
	def __init__(self, variable: Variable) -> None:
		super().__init__()
		self.variables = [] #type: List[Variable]
		# We exand this variabble right away. 
		# It seems that console messages that have a variable reference are an array of variables to display
		# the names of those variables are their index...
		@core.async
		def onVariables() -> core.awaitable[None]:
			self.variables = yield from variable.adapter.GetVariables(variable.reference)
			self.dirty()
		core.run(onVariables())

	def render(self) -> ui.components:
		items = []
		for v in self.variables:
			# we replace the name with the value... since the name is a number
			# this seems to be what vscode does
			v.name = v.value
			v.value = ''
			items.append(VariableComponent(v))
		return items


class EventLogComponent (ui.Component):
	def __init__(self):
		super().__init__()
		self.lines = [] #type: List[ui.Component]

	def AddVariable(self, variable: Variable) -> None:
		item = EventLogVariable(variable)
		self.lines.append(item)
		self.dirty()

	def Add(self, text: str) -> None:
		item = ui.Label(text, color = 'secondary')
		self.lines.append(item)
		self.dirty()

	def AddStdout(self, text: str) -> None:
		print('added output!')
		item = ui.Label(text, color = 'primary')
		self.lines.append(item)
		self.dirty()

	def AddStderr(self, text: str) -> None:
		item = ui.Label(text, color = 'red')
		self.lines.append(item)
		self.dirty()

	def clear(self) -> None:
		self.lines.clear()
		self.dirty()

	def render (self) -> ui.components:
		return [
			ui.HorizontalSpacer(300),
			ui.Panel(items = [
				ui.Segment(items = [
					ui.Label('Event Log', color="white")
				]),
				ui.Table(items = self.lines)
			])
		]