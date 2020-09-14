from ..typecheck import *
from ..import core

from .dap.session import (
	Watch,
)

from .terminals import (
	Terminal,
	TerminalProcess,
	TerminalTask,
	ExternalTerminal,
	ExternalTerminalTerminus,
	ExternalTerminalMacDefault,
	ExternalTerminalWindowsDefault,
)

from .import dap

from .breakpoints import Breakpoints

class DebuggerSessions (dap.SessionListener):
	def __init__(self):
		self.watch = Watch()

		self.terminals: List[Terminal] = []
		self.on_terminal_added: core.Event[Terminal] = core.Event()
		self.on_terminal_removed: core.Event[Terminal] = core.Event()

		self.external_terminals: List[ExternalTerminal] = []

		self.sessions: List[dap.Session] = []
		self.updated = core.Event()

		self.output = core.Event()
		self.transport_log = core.StdioLogger()

		self.on_updated_modules: core.Event[dap.Session] = core.Event()
		self.on_updated_sources: core.Event[dap.Session] = core.Event()
		self.on_updated_variables: core.Event[dap.Session] = core.Event()
		self.on_updated_threads: core.Event[dap.Session] = core.Event()
		self.on_added_session: core.Event[dap.Session] = core.Event()
		self.on_removed_session: core.Event[dap.Session] = core.Event()
		self.on_selected: core.Event[dap.Session] = core.Event()

		self.selected_session = None
		self.external_terminal_kind = 'platform'

	def __len__(self):
		return len(self.sessions)

	def __iter__(self):
		return iter(self.sessions)

	async def launch(self, breakpoints: Breakpoints, adapter: dap.AdapterConfiguration, configuration: dap.ConfigurationExpanded, restart: Optional[Any] = None, no_debug: bool = False):
		for session in self.sessions:
			if configuration.id_ish == session.configuration.id_ish:
				await session.stop()
				return

		session = dap.Session(
			breakpoints=breakpoints,
			watch=self.watch,
			listener=self,
			transport_log=self.transport_log,
		)
		@core.schedule
		async def run():
			self.sessions.append(session)
			self.on_added_session(session)

			await session.launch(adapter, configuration, restart, no_debug)
			await session.wait()
			session.dispose()
			self.remove_session(session)
		run()


	async def on_session_task_request(self, session: dap.Session, task: dap.TaskExpanded):
		# fixme ask Debugger to make the task instead
		import sublime
		terminal = TerminalTask(sublime.active_window(), task)
		if not terminal.background:
			self.add(session, terminal)

		await terminal.wait()

	async def on_session_terminal_request(self, session: dap.Session, request: dap.RunInTerminalRequest):
		await self.on_terminal_request(session, request)

	def on_session_state_changed(self, session: dap.Session, state: int):
		self.updated(session, state)

	def on_session_selected_frame(self, session: dap.Session, frame: Optional[dap.StackFrame]):
		self.selected_session = session
		self.updated(session, session.state)
		self.on_selected(session)

	def on_session_output_event(self, session: dap.Session, event: dap.OutputEvent):
		self.output(session, event)

	def on_session_updated_modules(self, session: dap.Session):
		self.on_updated_modules(session)

	def on_session_updated_sources(self, session: dap.Session):
		self.on_updated_sources(session)

	def on_session_updated_variables(self, session: dap.Session):
		self.on_updated_variables(session)

	def on_session_updated_threads(self, session: dap.Session):
		self.on_updated_threads(session)

	def remove_session(self, session: dap.Session):
		self.sessions.remove(session)
		self.on_removed_session(session)

		if self.selected_session == session:
			self.selected_session = None
			self.on_selected(session)

		self.updated(session, 0)

	def add(self, session: dap.Session, terminal: Terminal):
		self.terminals.append(terminal)
		self.on_terminal_added(terminal)

	def external_terminal(self, session: dap.Session, request: dap.RunInTerminalRequest) -> ExternalTerminal:
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

	async def on_terminal_request(self, session: dap.Session, request: dap.RunInTerminalRequest) -> dap.RunInTerminalResponse:
		if request.kind == 'integrated':
			terminal = TerminalProcess(request.cwd, request.args)
			self.add(session, terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=terminal.pid())

		if request.kind == 'external':
			external_terminal = self.external_terminal(session, request)
			self.external_terminals.append(external_terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=None)

		raise dap.Error(True, "unknown terminal kind requested '{}'".format(request.kind))

	def clear_session_data(self, session: dap.Session):
		...

	def clear_unused(self):
		for terminal in self.terminals:
			self.on_terminal_removed(terminal)
			terminal.dispose()

		self.terminals.clear()

		for external_terminal in self.external_terminals:
			external_terminal.dispose()
		self.external_terminals.clear()

	def dispose(self):
		self.clear_unused()

	@property
	def has_active(self):
		return bool(self.sessions)

	@property
	def active(self):
		if self.selected_session:
			return self.selected_session

		if self.sessions:
			return self.sessions[0]

		raise core.Error("No active debug sessions")

	@active.setter
	def active(self, session: dap.Session):
		self.selected_session = session
		self.updated(session, session.state)
		self.on_selected(session)

	def dispose(self):
		for terminal in self.terminals:
			terminal.dispose()

		for session in self.sessions:
			session.dispose()
