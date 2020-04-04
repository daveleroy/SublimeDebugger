from ..typecheck import *
from ..import core

from .debugger_session import (
	DebuggerSession,
	Variables,
	Watch,
	Terminals
)

from .adapter import Adapter, ConfigurationExpanded
from .breakpoints import Breakpoints

class DebuggerSessions:
	def __init__(self):
		self.threads = object()
		self.sources = object()
		self.modules = object()
		self.watch = Watch()
		self.variables = Variables()
		self.terminals = Terminals()

		self.sessions: List[DebuggerSession] = []
		self.updated = core.Event()

		self.output = core.Event()
		self.selected_frame = core.Event()
		self.transport_log = core.StdioLogger()

		self.on_updated_modules: core.Event[DebuggerSession] = core.Event()
		self.on_updated_sources: core.Event[DebuggerSession] = core.Event()
		self.on_updated_variables: core.Event[DebuggerSession] = core.Event()
		self.on_updated_threads: core.Event[DebuggerSession] = core.Event()
		self.on_added_session: core.Event[DebuggerSession] = core.Event()
		self.on_removed_session: core.Event[DebuggerSession] = core.Event()

		self.selected_session = None

	def __iter__(self):
		return iter(self.sessions)
	
	async def launch(self, breakpoints: Breakpoints, adapter: Adapter, configuration: ConfigurationExpanded, restart: Optional[Any] = None, no_debug: bool = False):

		def on_state_changed(session, value):
			self.updated(session, value)
		def on_output(session, value):
			self.output(session, value)
		def on_selected_frame(session, value):
			self.selected_session = session
			self.updated(session, session.state)

			self.selected_frame(session, value)

		session = DebuggerSession(
			breakpoints=breakpoints,
			threads=self.threads,
			watch=self.watch,
			variables=self.variables,
			terminals=self.terminals,
			on_state_changed=on_state_changed,
			on_output=on_output,
			on_selected_frame=on_selected_frame,
			transport_log=self.transport_log,
		)
		self.add_session(session)

		@core.schedule
		async def run():
			await session.launch(adapter, configuration, restart, no_debug)
			await session.wait()
			session.dispose()
			self.remove_session(session)
		run()

	def add_session(self, session: DebuggerSession):
		session.on_updated_modules.add(lambda: self.on_updated_modules(session))
		session.on_updated_sources.add(lambda: self.on_updated_sources(session))
		session.on_updated_variables.add(lambda: self.on_updated_variables(session))
		session.on_updated_threads.add(lambda: self.on_updated_threads(session))
		self.sessions.append(session)
		self.on_added_session(session)

	def remove_session(self, session: DebuggerSession):
		self.sessions.remove(session)
		self.on_removed_session(session)
		
		if self.selected_session == session:
			self.selected_session = None
			self.selected_frame(session, None)

		self.updated(session, 0)

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
	
	def dispose(self):
		for session in self.sessions:
			session.dispose()