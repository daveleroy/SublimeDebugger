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
		self.watch = Watch()
		self.terminals = Terminals()

		self.sessions: List[DebuggerSession] = []
		self.updated = core.Event()

		self.output = core.Event()
		self.transport_log = core.StdioLogger()

		self.on_updated_modules: core.Event[DebuggerSession] = core.Event()
		self.on_updated_sources: core.Event[DebuggerSession] = core.Event()
		self.on_updated_variables: core.Event[DebuggerSession] = core.Event()
		self.on_updated_threads: core.Event[DebuggerSession] = core.Event()
		self.on_added_session: core.Event[DebuggerSession] = core.Event()
		self.on_removed_session: core.Event[DebuggerSession] = core.Event()
		self.on_selected: core.Event[DebuggerSession] = core.Event()

		self.selected_session = None

	def __len__(self):
		return len(self.sessions)

	def __iter__(self):
		return iter(self.sessions)

	async def launch(self, breakpoints: Breakpoints, adapter: Adapter, configuration: ConfigurationExpanded, restart: Optional[Any] = None, no_debug: bool = False):
		for session in self.sessions:
			if configuration.id_ish == session.configuration.id_ish:
				await session.stop()

		def on_state_changed(session, value):
			self.updated(session, value)
		def on_output(session, value):
			self.output(session, value)
		def on_selected_frame(session, value):
			self.selected_session = session
			self.updated(session, session.state)
			self.on_selected(session)

		session = DebuggerSession(
			breakpoints=breakpoints,
			watch=self.watch,
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

		def on_updated_modules(): self.on_updated_modules(session)
		def on_updated_sources(): self.on_updated_sources(session)
		def on_updated_variables(): self.on_updated_variables(session)
		def on_updated_threads(): self.on_updated_threads(session)

		session.on_updated_modules.add(on_updated_modules)
		session.on_updated_sources.add(on_updated_sources)
		session.on_updated_variables.add(on_updated_variables)
		session.on_updated_threads.add(on_updated_threads)

		self.sessions.append(session)
		self.on_added_session(session)

	def remove_session(self, session: DebuggerSession):
		self.sessions.remove(session)
		self.on_removed_session(session)

		if self.selected_session == session:
			self.selected_session = None
			self.on_selected(session)

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

	@active.setter
	def active(self, session: DebuggerSession):
		self.selected_session = session
		self.updated(session, session.state)
		self.on_selected(session)

	def dispose(self):
		for session in self.sessions:
			session.dispose()
