from __future__ import annotations
from ...typecheck import *
from ...import core

from ..dap import types as dap
from ..dap import Variable, SourceLocation

from .terminal import Terminal
from ..panel import OutputPanel


import sublime

if TYPE_CHECKING:
	from ..debugger_session import DebuggerSession

class TermianlDebugger (Terminal):
	def __init__(self, window: sublime.Window, on_run_command: Callable[[str], None]):
		super().__init__("Debugger Console")
		self.on_run_command = on_run_command
		self.panel = OutputPanel(window, "Console", show_panel=False)

	def dispose(self):
		super().dispose()
		self.panel.dispose()

	def show_backing_panel(self):
		self.panel.open()

	def clear(self):
		super().clear()
		self.panel.clear()

	def writeable(self) -> bool:
		return True

	def writeable_prompt(self) -> str:
		return "click to input debugger command"

	def write(self, text: str):
		self.on_run_command(text)

	def program_output(self, session: DebuggerSession, event: dap.OutputEvent):
		variablesReference = event.variablesReference
		if variablesReference:
			# this seems to be what vscode does it ignores the actual message here.
			# Some of the messages are junk like "output" that we probably don't want to display
			async def appendVariabble() -> None:
				variables = await session.get_variables(variablesReference, without_names=True)
				for variable in variables:
					self.append_variable(session, variable, event.source, event.line)

			# this could make variable messages appear out of order. Do we care??
			core.run(appendVariabble())
		else:
			self.append_text(event.category, event.text, event.source, event.line)

	def append_variable(self, session: DebuggerSession, variable: dap.Variable, source: Optional[dap.Source], line: Optional[int]):
		if source:
			self.add_variable(variable, SourceLocation(source, line))
		else:
			self.add_variable(variable)

	def append_text(self, type: str, text: str, source: Optional[dap.Source], line: Optional[int]):
		if type == "telemetry":
			return

		self.panel.write(text)

		if source:
			self.add(type, text, SourceLocation(source, line))
		else:
			self.add(type, text)

	def log_error(self, text: str) -> None:
		self.append_text('debugger.error', text + '\n', None, None)

	def log_info(self, text: str) -> None:
		self.append_text('debugger.info', text + '\n', None, None)
