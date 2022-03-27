from __future__ import annotations
from .typecheck import *

from .import core, ui

import sublime

from .import dap
from .import persistance

from .settings import Settings
from .breakpoints import Breakpoints
from .project import Project
from .panel import DebuggerProtocolLogger

from .watch import Watch


class Debugger (dap.Debugger, dap.SessionListener, core.Logger):
	
	instances: dict[int, 'Debugger'] = {}
	creating: dict[int, bool] = {}

	@staticmethod
	def should_auto_open_in_window(window: sublime.Window) -> bool:
		if Settings.open_at_startup:
			if data := window.project_data():
				return 'debugger_configurations' in data

		return False

	@staticmethod
	def create(window: sublime.Window) -> Debugger:
		debugger = Debugger.get(window, True)
		assert debugger
		return debugger

	@staticmethod
	def get(window_or_view: sublime.Window|sublime.View, create: bool = False) -> Debugger|None:
		global instances
		if isinstance(window_or_view, sublime.View):
			window = window_or_view.window()
		else:
			window = window_or_view

		if window is None:
			return None

		id = window.id()
		instance = Debugger.instances.get(id)

		if not instance and create:
			if Debugger.creating.get(id):
				raise core.Error("We shouldn't be creating another debugger instance for this window...")

			Debugger.creating[id] = True
			try:
				instance = Debugger(window)
				Debugger.instances[id] = instance

			except core.Error:
				core.exception()

			Debugger.creating[id] = False

		if instance and create:
			instance.interface.open()

		return instance

	def __init__(self, window: sublime.Window) -> None:
		from .debugger_interface import DebuggerInterface

		self.on_error: core.Event[str] = core.Event()
		self.on_info: core.Event[str] = core.Event()

		self.on_session_added: core.Event[dap.Session] = core.Event()
		self.on_session_removed: core.Event[dap.Session] = core.Event()
		self.on_session_active: core.Event[dap.Session] = core.Event()

		self.on_session_modules_updated: core.Event[dap.Session] = core.Event()
		self.on_session_sources_updated: core.Event[dap.Session] = core.Event()
		self.on_session_variables_updated: core.Event[dap.Session] = core.Event()
		self.on_session_threads_updated: core.Event[dap.Session] = core.Event()
		self.on_session_state_updated: core.Event[dap.Session, dap.Session.State] = core.Event()
		self.on_session_output: core.Event[dap.Session, dap.OutputEvent] = core.Event()
		self.on_session_output: core.Event[dap.Session, dap.OutputEvent] = core.Event()

		self.on_session_run_terminal_requested: core.EventReturning[Awaitable[dap.RunInTerminalResponse], dap.Session, dap.RunInTerminalRequestArguments] = core.EventReturning()
		self.on_session_run_task_requested: core.EventReturning[Awaitable[None], dap.Session|None, dap.TaskExpanded] = core.EventReturning()


		self.session: dap.Session|None = None
		self.sessions: list[dap.Session] = []

		self.window = window
		self.disposeables: list[Any] = []

		self.last_run_task = None

		self.project = Project(window)
		self.transport_log = DebuggerProtocolLogger(self.window)

		self.breakpoints = Breakpoints()
		self.watch = Watch()		
		self.interface = DebuggerInterface(self, window)

		self.disposeables.extend([
			self.project,
			self.interface,
			self.transport_log,
			self.breakpoints,
		])

		self.load_data()


	async def launch(self, breakpoints: Breakpoints, adapter: dap.AdapterConfiguration, configuration: dap.ConfigurationExpanded, restart: Any|None = None, no_debug: bool = False, parent: dap.Session|None = None) -> dap.Session:
		for session in self.sessions:
			if configuration.id_ish == session.configuration.id_ish:
				await session.stop()
				# return

		session = dap.Session(
			adapter_configuration=adapter,
			configuration=configuration,
			restart=restart,
			no_debug=no_debug,
			breakpoints=breakpoints, 
			watch=self.watch, 
			listener=self, 
			transport_log=self,
			debugger=self,
			parent=parent)

		@core.schedule
		async def run():
			self.add_session(session)

			await session.launch()
			await session.wait()

			self.remove_session(session)
		run()

		return session

	async def on_session_task_request(self, session: dap.Session, task: dap.TaskExpanded):
		response = self.on_session_run_task_requested(session, task)
		if not response: raise core.Error('No run task response')
		return await response

	async def on_session_terminal_request(self, session: dap.Session, request: dap.RunInTerminalRequestArguments) -> dap.RunInTerminalResponse:
		response = self.on_session_run_terminal_requested(session, request)
		if not response: raise core.Error('No terminal session response')
		return await response

	def on_session_state_changed(self, session: dap.Session, state: dap.Session.State):
		self.on_session_state_updated(session, state)

	def on_session_selected_frame(self, session: dap.Session, frame: dap.StackFrame|None):
		self.session = session
		self.on_session_state_updated(session, session.state)
		self.on_session_active(session)

	def on_session_output_event(self, session: dap.Session, event: dap.OutputEvent):
		self.on_session_output(session, event)

	def on_session_updated_modules(self, session: dap.Session):
		self.on_session_modules_updated(session)

	def on_session_updated_sources(self, session: dap.Session):
		self.on_session_sources_updated(session)

	def on_session_updated_variables(self, session: dap.Session):
		self.on_session_variables_updated(session)

	def on_session_updated_threads(self, session: dap.Session):
		self.on_session_threads_updated(session)

	def add_session(self, session: dap.Session):
		self.sessions.append(session)
		# if a session is added select it
		self.session = session

		self.on_session_added(session)
		self.on_session_active(session)

	def remove_session(self, session: dap.Session):
		self.sessions.remove(session)
		session.dispose()

		if self.session == session:
			self.session = self.sessions[0] if self.sessions else None
		
			# try to select the first session with threads if there is one
			for session in self.sessions:
				if session.threads:
					self.session = session
					break

			self.on_session_active(session)

		self.on_session_state_updated(session, dap.Session.State.STOPPED)
		self.on_session_removed(session)

	@property
	def is_active(self):
		return self.session != None

	@property
	def active(self):
		if not self.session:
			raise core.Error("No Active Debug Sessions")
		return self.session

	@active.setter
	def active(self, session: dap.Session):
		self.session = session
		self.on_session_state_updated(session, session.state)
		self.on_session_active(session)

	def clear_all_breakpoints(self):
		self.breakpoints.data.remove_all()
		self.breakpoints.source.remove_all()
		self.breakpoints.function.remove_all()

	def show_protocol_panel(self):
		self.transport_log.show()

	def set_diagnostics(self, id: str, errors: Any) -> None:
		self.interface.problems_panel.update(id, errors)
		if not self.is_active:
			self.interface.middle_panel.select(self.interface.problems_panel)

	def set_configuration(self, configuration: Union[dap.Configuration, dap.ConfigurationCompound]):
		self.project.configuration_or_compound = configuration
		self.save_data()

	def dispose(self) -> None:
		self.save_data()
		for session in self.sessions:
			session.dispose()
		for d in self.disposeables:
			d.dispose()

		del Debugger.instances[self.window.id()]

	def run_async(self, awaitable: Awaitable[Any]):
		core.run(awaitable, on_error=lambda e: self.error(str(e)))

	def is_paused(self):
		return self.is_active and self.active.state == dap.Session.State.PAUSED

	def is_running(self):
		return self.is_active and self.active.state == dap.Session.State.RUNNING

	def is_stoppable(self):
		return self.is_active and self.active.state != dap.Session.State.STOPPED

	def run_to_current_line(self) -> None:
		raise core.Error("Not implemented right now...")
		# self.breakpoints_provider.run_to_current_line()

	def load_data(self):
		json = persistance.load(self.project.project_name)
		self.project.load_from_json(json.get('project', {}))
		self.breakpoints.load_from_json(json.get('breakpoints', {}))
		self.watch.load_json(json.get('watch', []))

	def save_data(self):
		json = {
			'project': self.project.into_json(),
			'breakpoints': self.breakpoints.into_json(),
			'watch': self.watch.into_json(),
		}
		persistance.save(self.project.project_name, json)

	def on_run_task(self) -> None:
		values: list[ui.InputListItem] = []
		for task in self.project.tasks:
			def run(task: dap.Task = task):
				self.last_run_task = task
				self.run_task(task)

			values.append(ui.InputListItem(run, task.name))

		ui.InputList(values, 'Select task to run').run()

	def on_run_last_task(self) -> None:
		if self.last_run_task:
			self.run_task(self.last_run_task)
		else:
			self.on_run_task()

	@core.schedule
	async def run_task(self, task: dap.Task):
		variables = self.project.extract_variables()
		await self.on_session_run_task_requested(None, dap.TaskExpanded(task, variables))
		
	# async def sessions_run_task(self, session: dap.Session, task: dap.TaskExpanded):
	# 	await self.run_task(task)

	def error(self, value: str):
		self.on_error(value)

	def info(self, value: str):
		self.on_info(value)

	def log(self, type: str, value: str):
		if type == 'transport':
			self.transport_log.info(value)
		else:
			self.on_info(value)

	def configurations_to_vscode_launch_json(self):
		json = self.project.configurations_as_vscode_launch_json()
		file = self.window.new_file()
		core.edit(file, lambda edit: file.insert(edit, file.size(), sublime.encode_value(json, True)))

	def refresh_phantoms(self) -> None:
		ui.Layout.render_layouts()
