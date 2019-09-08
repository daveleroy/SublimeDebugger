
from ..typecheck import *
from .terminal import TerminalStandard, Line, LineSourceComponent
from .. import dap, ui, core
from ..components.variable_component import VariableStatefulComponent, VariableStateful

class VariableLine(Line):
	def __init__(self, variable: dap.Variable, source: Optional[dap.Source], line: Optional[int], on_clicked_source: Callable[[], None])  -> None:
		self.variable = VariableStateful(variable, None)
		self.source = source
		self.line = line
		self.on_clicked_source = on_clicked_source

	def ui(self, layout, max_width) -> List[ui.Block]:
		source_item = None
		if self.source:
			variable_length = len(self.variable.name) + len(self.variable.value)
			text_width =  (max_width - variable_length) * layout.em_width() - 1.5
		

			source_item = LineSourceComponent(self.source.name, self.line, text_width, self.on_clicked_source)

		component = VariableStatefulComponent(self.variable, itemRight=source_item)

		# @FIXME this doesn't really work if there are multiple components being drawn for the same variable
		self.variable.on_dirty = component.dirty
		return [component]

class DebuggerTerminal (TerminalStandard):
	def __init__(self, on_run_command: Callable[[str], None], on_clicked_source: [[dap.Source, Optional[int]], None]):
		super().__init__("Debugger Console")
		self.on_run_command = on_run_command
		self.on_clicked_source = on_clicked_source

	def writeable(self) -> bool:
		return True

	def writeable_prompt(self) -> str:
		return "click to input debugger command"

	def write(self, text: str):
		self.on_run_command(text)

	def program_output(self, client: dap.DebugAdapterClient, event: dap.OutputEvent):
		variablesReference = event.variablesReference
		if variablesReference:
			# this seems to be what vscode does it ignores the actual message here.
			# Some of the messages are junk like "output" that we probably don't want to display
			@core.async
			def appendVariabble() -> core.awaitable[None]:
				variables = yield from client.GetVariables(variablesReference)
				for variable in variables:
					variable.name = "" # this is what vs code does?
					self.append_variable(variable, event.source, event.line)

			# this could make variable messages appear out of order. Do we care??
			 
			core.run(appendVariabble())
		else:
			self.append_text(event.category, event.text, event.source, event.line)

	def clicked_source(self, source: dap.Source, line: Optional[int]) -> None:
		self.on_clicked_source(source, line)

	def append_variable(self, variable: dap.Variable, source: Optional[dap.Source], line: Optional[int]):
		def on_clicked_source():
			self.on_clicked_source(source, line)
		self.lines.append(VariableLine(variable, source, line, on_clicked_source))
		self.on_updated()

	def append_text(self, type: str, text: str, source: Optional[dap.Source], line: Optional[int]):
		print(type, text, end=":")
		if type == "telemetry":
			return
		self._append(type, text, source, line)

	def log_error(self, text: str) -> None:
		self.append_text('debugger.error', text + '\n', None, None)

	def log_info(self, text: str) -> None:
		self.append_text('debugger.info', text + '\n', None, None)
