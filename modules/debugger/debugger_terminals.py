from ..typecheck import*
from ..import core
from ..import dap

from .terminal import Terminal, TerminalProcess
from .external_terminal import (
	ExternalTerminal,
	TerminusExternalTerminal,
	DefaultWindowsExternalTerminal,
	DefaultMacExternalTerminal,
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

	def create_terminal(self, request: dap.RunInTerminalRequest):
		terminal = TerminalProcess(request.cwd, request.args)
		self.terminals.append(terminal)
		self.on_terminal_added(terminal)

	def external_terminal(self, session: 'DebuggerSession', request: dap.RunInTerminalRequest) -> ExternalTerminal:
		title = request.title or session.configuration.name or '?'
		env = request.env or {}
		cwd = request.cwd
		commands = request.args

		if self.external_terminal_kind == 'platform':
			if core.platform.osx:
				return DefaultMacExternalTerminal(title, cwd, commands, env)
			if core.platform.windows:
				return DefaultWindowsExternalTerminal(title, cwd, commands, env)
			if core.platform.linux:
				raise core.Error('default terminal for linux not implemented')

		if self.external_terminal_kind == 'terminus':
			return TerminusExternalTerminal(title, cwd, commands, env)

		raise core.Error('unknown external terminal type "{}"'.format(self.external_terminal_kind))

	def on_terminal_request(self, session: 'DebuggerSession', request: dap.RunInTerminalRequest) -> dict:
		if request.kind == 'integrated':
			return self.create_terminal(request).pid()

		if request.kind == 'external':
			external_terminal = self.external_terminal(session, request)
			self.external_terminals.append(external_terminal)
			return {}

		return dap.Error(True, "unknown terminal kind requested '{}'".format(request.kind))

	def clear_session_data(self, session: 'DebuggerSession'):
		for terminal in self.terminals:
			self.on_terminal_removed(terminal)
		self.terminals.clear()

		for external_terminal in self.external_terminals:
			external_terminal.dispose()
		self.external_terminals.clear()
