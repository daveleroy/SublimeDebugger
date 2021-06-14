from __future__ import annotations
from ..typecheck import *
from ..import core

from .session import Session, SessionListener, Watch
from .configuration import AdapterConfiguration, ConfigurationExpanded, TaskExpanded
from .types import OutputEvent, StackFrame, RunInTerminalRequest, RunInTerminalResponse, Error
from ..breakpoints import Breakpoints

class SessionsTasksProvider (Protocol):
	async def sessions_create_terminal(self, session: Session, request: RunInTerminalRequest) -> RunInTerminalResponse:
		...
	async def sessions_run_task(self, session: Session, task: TaskExpanded):
		...

class Sessions (SessionListener):
	def __init__(self, provider: SessionsTasksProvider, log: core.Logger):
		self.watch = Watch()
		self.provider = provider

		self.sessions: list[Session] = []

		self.updated: core.Event[Session, Session.State] = core.Event()
		self.output: core.Event[Session, OutputEvent] = core.Event()
		
		self.log = log

		self.on_updated_modules: core.Event[Session] = core.Event()
		self.on_updated_sources: core.Event[Session] = core.Event()
		self.on_updated_variables: core.Event[Session] = core.Event()
		self.on_updated_threads: core.Event[Session] = core.Event()
		self.on_added_session: core.Event[Session] = core.Event()
		self.on_removed_session: core.Event[Session] = core.Event()
		self.on_selected: core.Event[Session] = core.Event()

		self.selected_session = None

	def __len__(self):
		return len(self.sessions)

	def __iter__(self):
		return iter(self.sessions)

	async def launch(self, breakpoints: Breakpoints, adapter: AdapterConfiguration, configuration: ConfigurationExpanded, restart: Any|None = None, no_debug: bool = False, parent: Session|None = None) -> Session:
		for session in self.sessions:
			if configuration.id_ish == session.configuration.id_ish:
				await session.stop()
				# return

		session = Session(
			adapter_configuration=adapter,
			configuration=configuration,
			restart=restart,
			no_debug=no_debug,
			breakpoints=breakpoints, 
			watch=self.watch, 
			listener=self, 
			transport_log=self.log, 
			parent=parent)

		@core.schedule
		async def run():
			self.add_session(session)

			await session.launch()

			await session.wait()
			session.dispose()
			self.remove_session(session)
		run()

	async def on_session_task_request(self, session: Session, task: TaskExpanded):
		await self.provider.sessions_run_task(session, task)

	async def on_session_terminal_request(self, session: Session, request: RunInTerminalRequest) -> RunInTerminalResponse:
		await self.provider.sessions_create_terminal(session, request)
		return RunInTerminalResponse(processId=None, shellProcessId=None)

	def on_session_state_changed(self, session: Session, state: Session.State):
		self.updated(session, state)

	def on_session_selected_frame(self, session: Session, frame: Optional[StackFrame]):
		self.selected_session = session
		self.updated(session, session.state)
		self.on_selected(session)

	def on_session_output_event(self, session: Session, event: OutputEvent):
		self.output(session, event)

	def on_session_updated_modules(self, session: Session):
		self.on_updated_modules(session)

	def on_session_updated_sources(self, session: Session):
		self.on_updated_sources(session)

	def on_session_updated_variables(self, session: Session):
		self.on_updated_variables(session)

	def on_session_updated_threads(self, session: Session):
		self.on_updated_threads(session)

	def add_session(self, session: Session):
		self.sessions.append(session)
		self.on_added_session(session)

		# if a session is added select it
		self.selected_session = session
		self.on_selected(session)

	def remove_session(self, session: Session):
		self.sessions.remove(session)
		self.on_removed_session(session)

		if self.selected_session == session:
			if self.sessions:
				self.selected_session = self.sessions[0]
			else:
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
	def active(self, session: Session):
		self.selected_session = session
		self.updated(session, session.state)
		self.on_selected(session)

	def dispose(self):
		for session in self.sessions:
			session.dispose()
