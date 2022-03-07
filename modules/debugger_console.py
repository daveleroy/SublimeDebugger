from __future__ import annotations
from .typecheck import *

import sublime

from .import core
from .import dap
from .import ui

from .views import css
from .views.variable import VariableComponent
from .console_output_view import ConsoleOutputView


class DebuggerConsole:
	def __init__(self, window: sublime.Window):
		self.on_input: core.Event[str] = core.Event()
		self.on_navigate: core.Event[dap.SourceLocation] = core.Event()

		self.window = window
		self.panel: ConsoleOutputView|None = None
		self.indent = ''

	def dispose(self):
		if self.panel:
			self.panel.dispose()

	def acquire_panel(self) -> ConsoleOutputView:
		if not self.panel or self.panel.is_closed:
			if self.panel:
				self.panel.dispose()
			self.panel = ConsoleOutputView(self.window, 'Debugger Console')
			self.panel.on_input = self.on_input
			self.panel.on_escape.add(self.dispose)

		return self.panel

	def show(self):
		panel = self.acquire_panel()
		self.window.focus_view(panel.view)

	def close(self):
		if self.panel:
			self.panel.close()
			
	def clear(self):
		self.indent = ''
		if self.panel:
			self.panel.clear()

	def program_output(self, session: dap.Session, event: dap.OutputEvent):
		panel = self.acquire_panel()
		variablesReference = event.variablesReference
		if variablesReference:
			# save a place for these phantoms to be written to since we have to evaluate them first
			# panel.write(self.indent)
			placeholder = panel.write_phantom_placeholder()

			# this seems to be what vscode does it ignores the actual message here.
			# Some of the messages are junk like 'output' that we probably don't want to display
			async def appendVariabble() -> None:
				try:
					assert variablesReference
					variables = await session.get_variables(variablesReference, without_names=True)

					for i, variable in enumerate(variables):
						self.append_variable(variable, event.source, event.line, placeholder(), i)


				# if a request is cancelled it is because the debugger session ended
				# In some cases the variable cannot be fetched since the debugger session was terminated because of the exception
				# However the exception message is actually important and needs to be shown to the user...
				except core.CancelledError:
					print('Unable to fetch variables: Cancelled')
					# todo: this should be inserted into the place the phantom was going to be
					self.append_text(event.category or 'console', self.indent + event.output, event.source, event.line)

			core.run(appendVariabble())
		else:
			at = panel.at()

			if event.group == 'end':
				self.indent = self.indent[:-1]

			self.append_text(event.category or 'console', self.indent + event.output, event.source, event.line)

			if event.group == 'start' or event.group == 'startCollapsed':
				self.indent += '\t'

	def append_variable(self, variable: dap.Variable, source: Optional[dap.Source], line: int|None, at: int, index: int):
		panel = self.acquire_panel()
		if source:
			location = dap.SourceLocation(source, line)
			# def on_clicked_source(location: dap.SourceLocation):
			# 	self.on_navigate(location)

			panel.phantom_block(at, index=index)[
				VariableComponent(variable)
			]
		else:
			panel.phantom_block(at, index=index)[
				VariableComponent(variable)
			]

	def append_text(self, type: str|None, text: str, source: Optional[dap.Source], line: int|None):
		if type == 'telemetry':
			return

		sequences_for_types: dict[str|None, str] = {
			'debugger.error': 'red',
			'stderr': 'red',
			'debugger.info': 'blue',
		}

		type = sequences_for_types.get(type)

		panel = self.acquire_panel()

		panel.write(text, type)

		if source:
			location = dap.SourceLocation(source, line)
			def on_clicked_source():
				assert source
				self.on_navigate(location)

			# panel.phantom_inline(panel.at() - 1) [
			# 	ui.div(height=2.8)[
			# 		ui.spacer(1),
			# 		ui.click(on_clicked_source, title=source.name or '??')[
			# 			ui.text(f'@{location.name}', css=css.label_placeholder)
			# 		]
			# 	]
			# ]


	def log_error(self, text: str) -> None:
		panel = self.acquire_panel()
		panel.write(text + '\n', 'red')

	def log_info(self, text: str) -> None:
		panel = self.acquire_panel()
		panel.write(text + '\n', 'blue')
