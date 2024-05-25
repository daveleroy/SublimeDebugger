from __future__ import annotations
from typing import Any, Iterable

import sublime

from .import core
from .import ui
from .import dap
from .import menus

from .settings import Settings
from .breakpoints import Breakpoints, SourceBreakpoint
from .project import Project
from .watch import Watch

from .console import ConsoleOutputPanel
from .callstack import CallstackOutputPanel
from .output_panel import OutputPanel

from .disassemble import DisassembleView

from .terminal_external import ExternalTerminal, ExternalTerminalTerminus, ExternalTerminalMacDefault, ExternalTerminalWindowsDefault
from .terminal_task import Tasks
from .terminal_integrated import TerminusIntegratedTerminal

from .source_navigation import SourceNavigationProvider

class Debugger (core.Dispose, dap.Debugger):

	debuggers_for_window: dict[int, Debugger|None] = {}

	@staticmethod
	def ignore(view: sublime.View) -> bool:
		return not bool(Debugger.debuggers_for_window)

	@staticmethod
	def debuggers() -> Iterable[Debugger]:
		return filter(lambda i: i != None, Debugger.debuggers_for_window.values()) # type: ignore

	@staticmethod
	def create(window_or_view: sublime.Window|sublime.View, skip_project_check = False) -> Debugger:
		debugger = Debugger.get(window_or_view, create=True, skip_project_check=skip_project_check)
		assert debugger
		return debugger

	@staticmethod
	def get(window_or_view: sublime.Window|sublime.View, create = False, skip_project_check = False) -> Debugger|None:
		window = window_or_view.window() if isinstance(window_or_view, sublime.View) else window_or_view
		if window is None:
			return None

		id = window.id()

		if id in Debugger.debuggers_for_window:
			instance = Debugger.debuggers_for_window[id]
			if not instance and create:
				raise core.Error('We shouldn\'t be creating another debugger instance for this window...')

			if instance and create:
				instance.open()

			return instance

		if not create:
			return None

		Debugger.debuggers_for_window[id] = None
		try:
			instance = Debugger(window, skip_project_check=skip_project_check)
			Debugger.debuggers_for_window[id] = instance
			return instance

		except Exception:
			core.exception()
			del Debugger.debuggers_for_window[id]


	def __init__(self, window: sublime.Window, skip_project_check = False) -> None:
		self.window = window

		self.on_session_added = core.Event[dap.Session]()
		self.on_session_removed = core.Event[dap.Session]()
		self.on_session_active = core.Event[dap.Session]()

		self.on_session_modules_updated = core.Event[dap.Session]()
		self.on_session_sources_updated = core.Event[dap.Session]()
		self.on_session_variables_updated = core.Event[dap.Session]()
		self.on_session_threads_updated = core.Event[dap.Session]()
		self.on_session_updated = core.Event[dap.Session]()
		self.on_session_output = core.Event[dap.Session, dap.OutputEvent]()
		self.on_output_panels_updated = core.Event[None]()

		self.on_session_updated.add(self._on_session_updated)
		self.on_session_output.add(self._on_session_output)
		self.on_session_active.add(self._on_session_active)

		self.session: dap.Session|None = None
		self.sessions: list[dap.Session] = []
		self.last_run_task = None


		self.run_to_current_line_breakpoint: SourceBreakpoint|None = None

		self.output_panels: list[OutputPanel] = []
		self.external_terminals: dict[dap.Session, list[ExternalTerminal]] = {}
		self.integrated_terminals: dict[dap.Session, list[TerminusIntegratedTerminal]] = {}
		self.memory_views: list[MemoryView] = []
		self.disassembly_view: DisassembleView|None = None

		self.project = Project(window, skip_project_check)
		self.breakpoints = Breakpoints()
		self.watch = Watch()

		self.source_provider = SourceNavigationProvider(self.project, self)

		self.tasks = Tasks()

		self.console: ConsoleOutputPanel = ConsoleOutputPanel(self)
		self.console.on_input.add(self.on_run_command)
		self.console.on_navigate.add(self._on_navigate_to_source)

		self.project.reload(self.console)

		if location := self.project.location:
			json = core.json.load_json_from_package_data(location)
			self.project.load_from_json(json.get('project', {}))
			self.breakpoints.load_from_json(json.get('breakpoints', {}))
			self.watch.load_json(json.get('watch', []))
		else:
			core.info('Not loading data, project is not associated with a location')

		self.project.on_updated.add(self._on_project_or_settings_updated)

		self.callstack = CallstackOutputPanel(self)

		self.dispose_add([
			self.project,
			self.breakpoints,
			self.tasks,
			self.source_provider,
			self.console,
			self.callstack,
		])

		if not self.project.location:
			self.console.log('warn', 'Debugger not associated with a sublime-project so breakpoints and other data will not be saved')

		self.console.open()
		self._refresh_none_debugger_output_panels()

	def dispose(self) -> None:
		self.save_data()

		if self.disassembly_view:
			self.disassembly_view.dispose()

		self.dispose_terminals()

		for session in self.sessions:
			session.dispose()

		super().dispose()

		del Debugger.debuggers_for_window[self.window.id()]

	def _refresh_none_debugger_output_panel(self, panel_name: str):
		name = panel_name.replace('output.', '')
		panel = Settings.integrated_output_panels.get(name)
		if not panel:
			return

		view = self.window.find_output_panel(name)
		if not view:
			return

		# this view was already added
		if view.settings().has('debugger'):
			return

		output_panel = OutputPanel(self, name, name=panel.get('name'), show_panel=False, show_tabs=True, show_tabs_top=panel.get('position') != 'bottom', create=False)
		self.dispose_add(output_panel)

	def updated_settings(self):
		self.project.reload(self.console)

	def _refresh_none_debugger_output_panels(self):
		for panel_name in self.window.panels():
			self._refresh_none_debugger_output_panel(panel_name)

	def add_output_panel(self, panel: OutputPanel):
		# force integrated terminals to sit between the console and callstack
		if isinstance(panel, TerminusIntegratedTerminal):
			self.output_panels.insert(1, panel)
		else:
			self.output_panels.append(panel)

		self.on_output_panels_updated()

	def remove_output_panel(self, panel: OutputPanel):
		if panel.is_open():
			self.console.open()

		self.output_panels.remove(panel)
		self.on_output_panels_updated()

	async def ensure_installed(self, configurations: list[dap.Configuration]):
		types: list[str] = []
		for configuration in configurations:
			if not configuration.type in types:
				types.append(configuration.type)

		all_adapters_installed = True

		for type in types:
			adapter_configuration = dap.AdapterConfiguration.get(type)
			if not adapter_configuration.installed_version:
				all_adapters_installed = False

				self.console.open()
				if sublime.ok_cancel_dialog(f'Debug adapter with type name "{adapter_configuration.type}" is not installed.\n Would you like to install it?', 'Install'):
					await dap.AdapterConfiguration.install_adapter(self.console, adapter_configuration, None)

		return all_adapters_installed

	@core.run
	async def start(self, no_debug: bool = False, args: dict[str, Any]|None = None):
		try:
			if args and 'configuration' in args:
				configuration = args['configuration']
				if isinstance(configuration, str):
					previous_configuration_or_compound = self.project.configuration_or_compound
					self.project.load_configuration(configuration)
					if not self.project.configuration_or_compound:
						raise core.Error(f'Unable to find the configuration with the name `{configuration}`')

					if self.project.configuration_or_compound != previous_configuration_or_compound:
						core.info('Saving data: configuration selection changed')
						self.save_data()

					configurations = self.project.active_configurations()

				else:
					configurations = [
						dap.Configuration.from_json(args['configuration'], -1)
					]

			else:
				configurations = self.project.active_configurations()
				if not configurations:
					self.console.error('Add or select a configuration to begin debugging')
					await menus.change_configuration(self)

				configurations = self.project.active_configurations()
				if not configurations:
					return

			await self.start_with_configurations(configurations, no_debug)

		except Exception as e:
			core.exception()
			core.display(e)

	@core.run
	async def start_with_configurations(self, configurations: list[dap.Configuration], no_debug: bool = False):

		# grab variables before we open the console because the console will become the focus
		# and then things like $file would point to the console
		variables = self.project.extract_variables()

		self.dispose_terminals(unused_only=True)

		# clear console if there are not any currently active sessions
		if not self.sessions:
			self.console.clear()

			# This just ensures the console flashes briefly before starting the session if the adapter is just going to instantly put the exact same contents as before such as during a startup error
			# Otherwise it can look like nothing happened
			await core.delay(1.0/30.0)

		self.console.open()

		if not await self.ensure_installed(configurations):
			return


		for configuration in configurations:
			@core.run
			async def launch(configuration: dap.Configuration):
				try:
					adapter_configuration = dap.AdapterConfiguration.get(configuration.type)
					configuration_expanded = dap.ConfigurationExpanded(configuration, variables)

					pre_debug_task = configuration_expanded.get('pre_debug_task')
					post_debug_task = configuration_expanded.get('post_debug_task')

					if pre_debug_task:
						configuration_expanded.pre_debug_task = dap.TaskExpanded(self.project.get_task(pre_debug_task), variables)

					if post_debug_task:
						configuration_expanded.post_debug_task = dap.TaskExpanded(self.project.get_task(post_debug_task), variables)

					await self.launch(self.breakpoints, adapter_configuration, configuration_expanded, no_debug=no_debug)
					self.console.open()

				except core.Error as e:
					self.console.open()

					if sublime.ok_cancel_dialog("Unable To Start Debug Session\n\n{}".format(str(e)), 'Open Project'):
						self.project.open_project_configurations_file()

			launch(configuration)

	async def launch(self, breakpoints: Breakpoints, adapter: dap.AdapterConfiguration, configuration: dap.ConfigurationExpanded, restart: Any|None = None, no_debug: bool = False, parent: dap.Session|None = None) -> dap.Session:
		for session in self.sessions:
			if configuration.id_ish == session.configuration.id_ish:
				await self.stop(session)
				# return

		session = dap.Session(
			adapter_configuration=adapter,
			configuration=configuration,
			restart=restart,
			no_debug=no_debug,
			breakpoints=breakpoints,
			watch=self.watch,
			debugger=self,
			parent=parent,
			console=self.console,
		)

		session.on_updated_modules = self.on_session_modules_updated
		session.on_updated_sources = self.on_session_sources_updated
		session.on_updated_threads = self.on_session_threads_updated
		session.on_updated_variables = self.on_session_variables_updated
		session.on_updated = self.on_session_updated
		session.on_output = self.on_session_output
		session.on_selected_frame = lambda session, _: self.set_current_session(session)
		session.on_finished = lambda session: self.remove_session(session)
		session.on_terminal_request = self.session_terminal_request
		session.on_task_request = self.session_task_request

		self.sessions.append(session)
		# if a session is added select it
		self.session = session

		self.on_session_added(session)
		self.on_session_active(session)

		await session.launch()
		return session

	@property
	def current_session(self):
		if not self.session:
			raise dap.NoActiveSessionError()
		return self.session

	def set_current_session(self, session: dap.Session):
		self.current_session = session

	@current_session.setter
	def current_session(self, session: dap.Session):
		self.session = session
		self.on_session_updated(session)
		self.on_session_active(session)

	async def session_task_request(self, session: dap.Session, task: dap.TaskExpanded):
		return await self.tasks.run(self, task)

	async def session_terminal_request(self, session: dap.Session, request: dap.RunInTerminalRequestArguments) -> dap.RunInTerminalResponse:
		response = self._on_session_run_terminal_requested(session, request)
		if not response: raise core.Error('No terminal session response')
		return await response

	def _on_session_updated(self, session: dap.Session):

		if self.session and self.session != session:
			return

		if session.state == dap.Session.State.PAUSED:
			if not session.stepping:
				self.callstack.open()

		if session.state.previous == dap.Session.State.PAUSED and session.state == dap.Session.State.RUNNING:
			if not session.stepping:
				if terminals := self.integrated_terminals.get(session):
					terminals[0].open()
				else:
					self.console.open()

	def _on_session_output(self, session: dap.Session, event: dap.OutputEvent):

		self.console.program_output(session, event)

	def remove_session(self, session: dap.Session):
		session.dispose()

		self.sessions.remove(session)
		self.on_session_removed(session)

		# select a new session if there is one
		if self.session == session:
			self.session = self.sessions[0] if self.sessions else None

			# try to select the first session with threads if there is one
			for s in self.sessions:
				if s.threads:
					self.session = s
					break

			self.on_session_active(session)


		if session.stopped_unexpectedly:
			found_error = False
			for data in self.console.protocol.logs:
				if isinstance(data, dap.TransportOutputLog):
					found_error = True
					self.console.error(data.output)

			# color the end prompt as an error if there were no errors found
			if not found_error:
				self.console.error('Debugging ended unexpectedly')
			else:
				self.console.info('Debugging ended unexpectedly')

		elif not self.sessions:
			self.console.info('Debugging ended')

		if not self.sessions:
			# if the debugger panel is open switch to the console.
			# note: We could be on a pre debug step panel which we want to remain on so only do this if we are on the callstack panel
			if self.callstack.is_open():
				self.console.open()

	def stepping_granularity(self):
		if not self.disassembly_view:
			return None

		view = self.disassembly_view.view
		window = view.window()
		if not window:
			return None

		if window.active_view() != view:
			return None

		return 'instruction'

	@core.run
	async def resume(self) -> None:
		try:
			await self.current_session.resume()
		except core.Error as e:
			self.console.error(f'Unable to continue: {e}')

	@core.run
	async def reverse_continue(self) -> None:
		try:
			await self.current_session.reverse_continue()
		except core.Error as e:
			self.console.error(f'Unable to reverse continue: {e}')

	@core.run
	async def pause(self) -> None:
		try:
			await self.current_session.pause()
		except core.Error as e:
			self.console.error(f'Unable to pause: {e}')

	@core.run
	async def step_over(self) -> None:
		try:
			await self.current_session.step_over(granularity=self.stepping_granularity())
		except core.Error as e:
			self.console.error(f'Unable to step over: {e}')

	@core.run
	async def step_in(self) -> None:
		try:
			await self.current_session.step_in(granularity=self.stepping_granularity())
		except core.Error as e:
			self.console.error(f'Unable to step in: {e}')

	@core.run
	async def step_out(self) -> None:
		try:
			await self.current_session.step_out(granularity=self.stepping_granularity())
		except core.Error as e:
			self.console.error(f'Unable to step out: {e}')

	@core.run
	async def step_back(self) -> None:
		try:
			await self.current_session.step_back(granularity=self.stepping_granularity())
		except core.Error as e:
			self.console.error(f'Unable to step backwards: {e}')

	@core.run
	async def stop(self, session: dap.Session|None = None) -> None:
		# the stop command stops all sessions in a hierachy
		try:
			if not session:
				root = self.current_session
				while root.parent:
					root = root.parent

				self.stop(root)
				return

			session_stop = session.stop()
			for child in session.children:
				self.stop(child)

			await session_stop

		except dap.NoActiveSessionError: ...
		except core.Error as e: self.console.error(f'Unable to stop: {e}')


	def clear_all_breakpoints(self):
		self.breakpoints.data.remove_all()
		self.breakpoints.source.remove_all()
		self.breakpoints.function.remove_all()

	def is_paused(self):
		return bool(self.session and self.session.is_paused)

	def is_paused_and_reversable(self):
		return self.is_paused() and bool(self.current_session.capabilities.supportsStepBack)

	def is_running(self):
		return bool(self.session and self.session.is_running)

	def is_stoppable(self):
		return bool(self.session and self.session.is_stoppable)

	def run_to_current_line(self) -> None:
		if self.run_to_current_line_breakpoint:
			self.breakpoints.source.remove(self.run_to_current_line_breakpoint)

		file, line, column = self.project.current_file_line_column()
		self.run_to_line_breakpoint = self.breakpoints.source.add_breakpoint(file, line, column)

	def save_data(self):
		location = self.project.location
		if not location:
			core.info('Not saving project data, project not associated with a location')
			return

		json = {
			'project': self.project.into_json(),
			'breakpoints': self.breakpoints.into_json(),
			'watch': self.watch.into_json(),
		}
		core.json.save_json_to_package_data(location, json)

	def on_run_task(self) -> None:
		values: list[ui.InputListItem] = []
		for task in self.project.tasks:
			def run(task: dap.Task = task):
				self.last_run_task = task
				self.run_task(task)

			values.append(ui.InputListItem(run, task.name))

		ui.InputList('Select task to run')[
			values
		].run()

	def on_run_last_task(self) -> None:
		if self.last_run_task:
			self.run_task(self.last_run_task)
		else:
			self.on_run_task()

	@core.run
	async def run_task(self, task: dap.Task):
		self.dispose_terminals(unused_only=True)
		variables = self.project.extract_variables()
		await self.tasks.run(self, dap.TaskExpanded(task, variables))

	def refresh_phantoms(self) -> None:
		ui.Layout.render_layouts()

	@core.run
	async def on_run_command(self, command: str) -> None:
		try:
			result = await self.current_session.evaluate_expression(command, context='repl')
			if result.variablesReference:
				self.console.write(f'', 'blue', ensure_new_line=True)
				self.console.write_variable(dap.Variable.from_evaluate(self.current_session, '', result), self.console.at())
			elif result.result:
				self.console.write(result.result, 'blue', ensure_new_line=True)
			else:
				core.debug('discarded evaluated expression empty result')

		except core.Error as e:
			self.console.error(f'{e}')

	@core.run
	async def evaluate_selected_expression(self):
		if view := sublime.active_window().active_view():
			sel = view.sel()[0]
			expression = view.substr(sel)
			self.on_run_command(expression)

	def toggle_breakpoint(self):
		file, line, _ = self.project.current_file_line_column()
		self.breakpoints.source.toggle(file, line)

	def toggle_column_breakpoint(self):
		file, line, column = self.project.current_file_line_column()
		self.breakpoints.source.toggle(file, line, column)

	def add_function_breakpoint(self):
		self.breakpoints.function.add_command()

	def add_watch_expression(self):
		self.watch.add_command()

	def on_input_command(self) -> None:
		self.console.open()
		self.console.enter()

	def _on_project_or_settings_updated(self):
		for panel in self.output_panels:
			panel.update_settings()

	def _on_session_active(self, session: dap.Session):
		if not self.session:
			self.source_provider.clear()
			return

		active_session = self.current_session
		thread = active_session.selected_thread
		frame = active_session.selected_frame

		if thread and frame and frame.source:
			self.source_provider.select_source_location(dap.SourceLocation(frame.source, frame.line, frame.column), thread)
		else:
			self.source_provider.clear()

	async def _on_session_run_terminal_requested(self, session: dap.Session, request: dap.RunInTerminalRequestArguments) -> dap.RunInTerminalResponse:
		title = request.title or session.configuration.name
		env = request.env or {}
		cwd = request.cwd
		commands = request.args

		if request.kind == 'external':
			def external_terminal():
				if self.project.external_terminal_kind == 'platform':
					if core.platform.osx:
						return ExternalTerminalMacDefault(title, cwd, commands, env)
					elif core.platform.windows:
						return ExternalTerminalWindowsDefault(title, cwd, commands, env)
					elif core.platform.linux:
						raise core.Error('default terminal for linux not implemented')
					else:
						raise core.Error('unreachable')

				if self.project.external_terminal_kind == 'terminus':
					return ExternalTerminalTerminus(title, cwd, commands, env)

				raise core.Error('unknown external terminal type "{}"'.format(self.project.external_terminal_kind))

			terminal = external_terminal()
			self.external_terminals.setdefault(session, []).append(terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=None)

		if request.kind == 'integrated':
			terminal = TerminusIntegratedTerminal(self, request.title or 'Untitled', request.cwd, request.args, request.env)
			self.integrated_terminals.setdefault(session, []).append(terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=None)

		raise core.Error('unknown terminal kind requested "{}"'.format(request.kind))

	def dispose_terminals(self, unused_only: bool=False):
		removed_sessions: list[dap.Session] = []

		for session, terminals in self.integrated_terminals.items():
			if not unused_only or session.state == dap.Session.State.STOPPED:
				removed_sessions.append(session)
				for terminal in terminals:
					terminal.dispose()

		for session, terminals in self.external_terminals.items():
			if not unused_only or session.state == dap.Session.State.STOPPED:
				removed_sessions.append(session)
				for terminal in terminals:
					terminal.dispose()

		for session in removed_sessions:
			try: del self.external_terminals[session]
			except KeyError:...

			try: del self.integrated_terminals[session]
			except KeyError:...

		self.tasks.remove_finished()

	def is_open(self):
		for panel in self.output_panels:
			if panel.is_open():
				return True
		return False

	def open(self) -> None:
		if not self.session:
			self.console.open()
		else:
			self.callstack.open()


	def show_disassembly(self, toggle: bool = False):
		if not self.disassembly_view:
			self.disassembly_view = DisassembleView(self.window, self)
			return

		view = self.disassembly_view.view
		window = view.window()

		# view is currently visible so toggle the view off
		if toggle and window and view.sheet() in window.selected_sheets():
			self.disassembly_view.dispose()
			self.disassembly_view = None
			return

		# recreate the view
		self.disassembly_view.dispose()
		self.disassembly_view = DisassembleView(self.window, self)


	def _on_navigate_to_source(self, source: dap.SourceLocation):
		self.source_provider.show_source_location(source)

	# Configuration Stuff
	def set_configuration(self, configuration: dap.Configuration|dap.ConfigurationCompound):
		self.project.configuration_or_compound = configuration
		self.project.on_updated()
		self.save_data()
