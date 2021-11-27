from __future__ import annotations
from .typecheck import *

from .import core
from .import dap
from .import ui

from .views import css
from .views.variable import VariableComponent
from .output_view import OutputView
import sublime

class DebuggerConsole:
	def __init__(self, window: sublime.Window, on_navigate: Callable[[dap.SourceLocation], None]):
		self.on_navigate = on_navigate
		self.window = window
		self.panel: OutputView|None = None
		self.indent = ''

	def dispose(self):
		if self.panel:
			self.panel.dispose()

	def acquire_panel(self) -> OutputView:
		if not self.panel or self.panel.is_closed:
			if self.panel:
				self.panel.dispose()
			self.panel = OutputView(self.window, 'Debugger Console')

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
			panel.write(self.indent)
			at = panel.write_phantom_placeholder()

			# this seems to be what vscode does it ignores the actual message here.
			# Some of the messages are junk like 'output' that we probably don't want to display
			async def appendVariabble(at: int) -> None:
				try:
					variables = await session.get_variables(variablesReference, without_names=True)

					for i, variable in enumerate(variables):
						self.append_variable(variable, event.source, event.line, at, i)


				# if a request is cancelled it is because the debugger session ended
				# In some cases the variable cannot be fetched since the debugger session was terminated because of the exception
				# However the exception message is actually important and needs to be shown to the user...
				except core.CancelledError:
					print('Unable to fetch variables: Cancelled')
					# todo: this should be inserted into the place the phantom was going to be
					self.append_text(event.category, self.indent + event.text, event.source, event.line)

			core.run(appendVariabble(at))
		else:
			at = panel.at()

			if event.group == 'end':
				self.indent = self.indent[:-1]

			self.append_text(event.category, self.indent + event.text, event.source, event.line)

			if event.group == 'start' or event.group == 'startCollapsed':
				self.indent += '\t'

	def append_variable(self, variable: dap.Variable, source: Optional[dap.Source], line: int|None, at: int, index: int):
		panel = self.acquire_panel()
		panel.write_phantom(ui.div(width=75)[
			VariableComponent(variable)
		], at=at, index=index*2)

		if source:
			def on_clicked_source():
				self.on_navigate(dap.SourceLocation(source, line))

			source_text = source.name or '??'
			item = ui.div(height=css.line_height)[
				ui.click(on_clicked_source, title=source_text)[
					ui.text(' ↗', css=css.label_secondary)
				],
			]
			panel.write_phantom(item, at, index=index*2 + 1)


	def append_text(self, type: str, text: str, source: Optional[dap.Source], line: int|None):
		if type == 'telemetry':
			return

		panel = self.acquire_panel()

		if source:
			def on_clicked_source():
				self.on_navigate(dap.SourceLocation(source, line))

			source_text = source.name or '??'
			item = ui.div(height=css.line_height)[
				ui.click(on_clicked_source, title=source_text)[
					ui.text('↗', css=css.label_secondary)
				]
			]
			panel.write(text, type)
		else:
			panel.write(text, type)

	def log_error(self, text: str) -> None:
		self.append_text('debugger.error', text + '\n', None, None)

	def log_info(self, text: str) -> None:
		self.append_text('debugger.info', text + '\n', None, None)
