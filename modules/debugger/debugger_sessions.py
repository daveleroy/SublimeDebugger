from ..typecheck import *
from ..import core

from .dap.session import (
	Watch,
	Terminals
)

from .adapter import AdapterConfiguration, ConfigurationExpanded

from .import dap

from .breakpoints import Breakpoints


class DebuggerSessions (dap.SessionListener):
	def __init__(self):
		self.watch = Watch()
		self.terminals = Terminals()

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
		for session in self.sessions:
			session.dispose()
