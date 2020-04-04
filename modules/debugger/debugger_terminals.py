from ..typecheck import*
from ..import core
from ..import dap

from .terminals import (
	ExternalTerminal,
	ExternalTerminalTerminus,
	ExternalTerminalWindowsDefault,
	ExternalTerminalMacDefault,

	Terminal,
	TerminalProcess,
)

if TYPE_CHECKING:
	from .debugger_session import DebuggerSession


class Terminals:
	def __init__(self):
		self.on_updated = core.Event() #type: core.Event[None]

		self.terminals = [] #type: List[Terminal]
		self.on_terminal_added = core.Event() #type: core.Event[Terminal]
		self.on_terminal_removed = core.Event() #type: core.Event[Terminal]

		self.external_terminals = [] #type: List[ExternalTerminal]
		self.external_terminal_kind = 'platform'

	def add(self, session: 'DebuggerSession', terminal: Terminal):
		self.terminals.append(terminal)
		self.on_terminal_added(terminal)

	def external_terminal(self, session: 'DebuggerSession', request: dap.RunInTerminalRequest) -> ExternalTerminal:
		title = request.title or session.configuration.name or '?'
		env = request.env or {}
		cwd = request.cwd
		commands = request.args

		if self.external_terminal_kind == 'platform':
			if core.platform.osx:
				return ExternalTerminalMacDefault(title, cwd, commands, env)
			if core.platform.windows:
				return ExternalTerminalWindowsDefault(title, cwd, commands, env)
			if core.platform.linux:
				raise core.Error('default terminal for linux not implemented')

		if self.external_terminal_kind == 'terminus':
			return ExternalTerminalTerminus(title, cwd, commands, env)

		raise core.Error('unknown external terminal type "{}"'.format(self.external_terminal_kind))

	def on_terminal_request(self, session: 'DebuggerSession', request: dap.RunInTerminalRequest) -> dap.RunInTerminalResponse:
		if request.kind == 'integrated':
			terminal = TerminalProcess(request.cwd, request.args)
			self.add(session, terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=terminal.pid())

		if request.kind == 'external':
			external_terminal = self.external_terminal(session, request)
			self.external_terminals.append(external_terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=None)

		raise dap.Error(True, "unknown terminal kind requested '{}'".format(request.kind))

	def clear_session_data(self, session: 'DebuggerSession'):
		...

	def clear_unused(self):
		for terminal in self.terminals:
			self.on_terminal_removed(terminal)
		self.terminals.clear()

		for external_terminal in self.external_terminals:
			external_terminal.dispose()
		self.external_terminals.clear()
