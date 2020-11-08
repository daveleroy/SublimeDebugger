from ..typecheck import *
from ..import core, ui

import sublime
import os
import webbrowser

from .import dap

from .autocomplete import Autocomplete
from .config import PersistedData
from .breakpoints import Breakpoints
from .project import Project
from .panel import DebuggerOutputPanel, DebuggerProtocolLogger

from .adapter import (
	Adapters,
)

from .terminals import (
	Terminal,
	TerminalProcess,
	TermianlDebugger,
	TerminalTask,
	ExternalTerminal,
	ExternalTerminalTerminus,
	ExternalTerminalMacDefault,
	ExternalTerminalWindowsDefault,
)

from .view_hover import ViewHoverProvider
from .source_navigation import SourceNavigationProvider
from .breakpoint_commands import BreakpointCommandsProvider

from .views.modules import ModulesView
from .views.sources import SourcesView
from .views.callstack import CallStackView

from .views.debugger_panel import DebuggerPanel
from .views.breakpoints_panel import BreakpointsPanel
from .views.variables_panel import VariablesPanel
from .views.tabbed_panel import TabbedPanel, TabbedPanelItem
from .views.selected_line import SelectedLine
from .views.terminal import TerminalView
from .views.problems import ProblemsView


class Debugger (dap.SessionsTasksProvider):

	instances = {} #type: Dict[int, Debugger]
	creating = {} #type: Set[int, bool]

	@staticmethod
	def should_auto_open_in_window(window: sublime.Window) -> bool:
		data = window.project_data()
		if not data:
			return False

		if "debugger_configurations" in data:
			return True

		return False

	@staticmethod
	def get(window: sublime.Window, create: bool = False) -> 'Optional[Debugger]':
		global instances
		id = window.id()
		instance = Debugger.instances.get(id)

		if not instance and create:
			if Debugger.creating.get(id):
				raise core.Error("We shouldn't be creating another debugger instance for this window...")

			Debugger.creating[id] = True
			try:
				instance = Debugger(window)
				Debugger.instances[id] = instance

			except dap.Error as e:
				core.log_exception()

			Debugger.creating[id] = False

		if instance and create:
			instance.show()

		return instance

	def __init__(self, window: sublime.Window) -> None:
		self.window = window
		self.disposeables = [] #type: List[Any]

		def on_project_configuration_updated():
			self.panel.set_ui_scale(self.project.ui_scale)
			self.debugger_panel.dirty()

		self.project = Project(window)
		self.project.on_updated.add(on_project_configuration_updated)

		self.panel = DebuggerOutputPanel(window)
		self.panel.set_ui_scale(self.project.ui_scale)

		self.disposeables.extend([
			self.project,
			self.panel,
		])

		self.transport_log = DebuggerProtocolLogger(self.window)
		self.disposeables.append(self.transport_log)
		autocomplete = Autocomplete.create_for_window(window)

		self.last_run_task = None
		self.external_terminals: List[ExternalTerminal] = []

		def on_output(session: dap.Session, event: dap.OutputEvent) -> None:
			self.terminal.program_output(session, event)

		def on_terminal_added(terminal: Terminal):
			if isinstance(terminal, TerminalTask):
				component = ProblemsView(terminal, self.on_navigate_to_source)
			else:
				component = TerminalView(terminal, self.on_navigate_to_source)

			panel = TabbedPanelItem(id(terminal), component, terminal.name(), 0, show_options=lambda: terminal.show_backing_panel())
			def on_modified():
				...
				#self.middle_panel.modified(panel)

			terminal.on_updated.add(on_modified)

			self.middle_panel.add(panel)
			self.middle_panel.select(id(terminal))

		def on_terminal_removed(terminal: Terminal):
			self.middle_panel.remove(id(terminal))

		self.breakpoints = Breakpoints()
		self.disposeables.append(self.breakpoints)

		self.sessions = dap.Sessions(self)
		self.sessions.transport_log = self.transport_log
		self.sessions.output.add(on_output)

		self.disposeables.append(self.sessions)

		self.terminal = TermianlDebugger(
			self.window,
			on_run_command=self.on_run_command,
		)
		self.terminals: List[Terminal] = []

		self.disposeables.append(self.terminal)

		self.source_provider = SourceNavigationProvider(self.project, self.sessions)
		self.view_hover_provider = ViewHoverProvider(self.project, self.sessions)
		self.breakpoints_provider = BreakpointCommandsProvider(self.project, self.sessions, self.breakpoints)
		self.disposeables.extend([self.view_hover_provider, self.source_provider, self.breakpoints_provider])

		self.persistance = PersistedData(self.project.name)
		self.load_data()

		self.terminal.log_info('Opened In Workspace: {}'.format(os.path.dirname(self.project.name)))

		#left panels
		self.breakpoints_panel = BreakpointsPanel(self.breakpoints, self.on_navigate_to_source)
		self.debugger_panel = DebuggerPanel(self, self.breakpoints_panel)

		# middle panels
		self.middle_panel = TabbedPanel([], 0, width_scale=0.666, width_additional=-41)

		self.terminal_view = TerminalView(self.terminal, self.on_navigate_to_source)

		self.callstack_view =  CallStackView(self.sessions)
		self.middle_panel.update([
			TabbedPanelItem(self.terminal_view, self.terminal_view, 'Debugger Console', show_options=lambda: self.terminal.show_backing_panel()),
			TabbedPanelItem(self.callstack_view, self.callstack_view, 'Callstack'),
		])

		# right panels
		self.right_panel = TabbedPanel([], 0, width_scale=0.333, width_additional=-41)

		self.variables_panel = VariablesPanel(self.sessions)
		self.modules_panel = ModulesView(self.sessions)
		self.sources_panel = SourcesView(self.sessions, self.on_navigate_to_source)

		self.right_panel.update([
			TabbedPanelItem(self.variables_panel, self.variables_panel, 'Variables'),
			TabbedPanelItem(self.modules_panel, self.modules_panel, 'Modules'),
			TabbedPanelItem(self.sources_panel, self.sources_panel, 'Sources'),
		])

		self.update_modules_visibility()
		self.update_sources_visibility()

		# phantoms
		phantom_location = self.panel.panel_phantom_location()
		phantom_view = self.panel.panel_phantom_view()

		self.left = ui.Phantom(self.debugger_panel, phantom_view, sublime.Region(phantom_location, phantom_location), sublime.LAYOUT_INLINE)
		self.middle = ui.Phantom(self.middle_panel, phantom_view, sublime.Region(phantom_location + 0, phantom_location + 1), sublime.LAYOUT_INLINE)
		self.right = ui.Phantom(self.right_panel, phantom_view, sublime.Region(phantom_location + 0, phantom_location + 2), sublime.LAYOUT_INLINE)
		self.disposeables.extend([self.left, self.middle, self.right])

		self.sessions.on_updated_modules.add(lambda _: self.update_modules_visibility())
		self.sessions.on_updated_sources.add(lambda _: self.update_sources_visibility())
		self.sessions.on_removed_session.add(self.on_session_removed)
		self.sessions.updated.add(self.on_session_state_changed)
		self.sessions.on_selected.add(self.on_session_selection_changed)

		on_project_configuration_updated()

	def on_session_removed(self, session: dap.Session):
		self.update_sources_visibility()
		self.update_modules_visibility()

	def on_session_selection_changed(self, session: dap.Session):
		if not self.sessions.has_active:
			self.source_provider.clear()
			return

		active_session = self.sessions.active
		thread = active_session.selected_thread
		frame = active_session.selected_frame

		if thread and frame and frame.source:
			self.source_provider.select_source_location(dap.SourceLocation(frame.source, frame.line, frame.column), thread.stopped_reason or "Stopped")
		else:
			self.source_provider.clear()

	def on_session_state_changed(self, session: dap.Session, state):
		if state == dap.Session.stopped:
			if self.sessions or session.stopped_reason == dap.Session.stopped_reason_build_failed:
				... # leave build results open or there is still a running session
			else:
				self.show_console_panel()

		elif state == dap.Session.running:
			self.show_console_panel()

		elif state == dap.Session.paused:
			# if self.project.bring_window_to_front_on_pause:
			# figure out a good way to bring sublime to front

			self.show_call_stack_panel()

		elif state == dap.Session.stopping or state == dap.Session.starting:
			...

	def update_sources_visibility(self):
		has_sources = False
		for session in self.sessions:
			if session.sources:
				has_sources = True
				break

		self.right_panel.set_visible(self.sources_panel, has_sources)

	def update_modules_visibility(self):
		has_modules = False
		for session in self.sessions:
			if session.modules:
				has_modules = True
				break

		self.right_panel.set_visible(self.modules_panel, has_modules)

	def show(self) -> None:
		self.panel.panel_show()

	def is_panel_visible(self) -> bool:
		return self.panel.is_panel_visible()

	def show_console_panel(self) -> None:
		self.middle_panel.select(self.terminal_view)

	def show_call_stack_panel(self) -> None:
		self.middle_panel.select(self.callstack_view)

	def set_configuration(self, configuration: Union[dap.Configuration, dap.ConfigurationCompound]):
		self.project.configuration_or_compound = configuration
		self.save_data()

	def open_project_configurations_file(self):
		self.project.open_project_configurations_file()

	def dispose(self) -> None:
		self.save_data()
		for d in self.disposeables:
			d.dispose()
		for terminal in self.terminals:
			terminal.dispose()

		del Debugger.instances[self.window.id()]

	def run_async(self, awaitable: Awaitable[core.T]):
		def on_error(e: Exception) -> None:
			self.terminal.log_error(str(e))
		core.run(awaitable, on_error=on_error)

	def on_navigate_to_source(self, source: dap.SourceLocation):
		self.source_provider.show_source_location(source)

	async def _on_play(self, no_debug=False) -> None:
		self.show_console_panel()
		self.terminal.clear()
		self.terminal.log_info('Console cleared...')
		try:
			active_configurations = self.project.active_configurations()
			if not active_configurations:
				self.terminal.log_error("Add or select a configuration to begin debugging")
				await self.change_configuration()

			active_configurations = self.project.active_configurations()
			if not active_configurations:
				return

		except Exception as e:
			core.log_exception()
			core.display(e)
			return

		variables = self.project.extract_variables()

		for configuration in active_configurations:
			@core.schedule
			async def launch():
				try:
					adapter_configuration = Adapters.get(configuration.type)
					configuration_expanded = dap.ConfigurationExpanded(configuration, variables)

					if configuration_expanded.get('pre_debug_task'):
						pre_debug_task = configuration_expanded.get('pre_debug_task')
						configuration_expanded.pre_debug_task = dap.TaskExpanded(self.project.get_task(pre_debug_task), variables)

					if configuration_expanded.get('post_debug_task'):
						post_debug_task = configuration_expanded.get('post_debug_task')
						configuration_expanded.post_debug_task = dap.TaskExpanded(self.project.get_task(post_debug_task), variables)

					if not adapter_configuration.installed_version:
						install = 'Debug adapter with type name "{}" is not installed.\n Would you like to install it?'.format(adapter_configuration.type)
						if sublime.ok_cancel_dialog(install, 'Install'):
							await adapter_configuration.install(self)

					await self.sessions.launch(self.breakpoints, adapter_configuration, configuration_expanded, no_debug=no_debug)
				except core.Error as e:
					if sublime.ok_cancel_dialog("Error Launching Configuration\n\n{}".format(str(e)), 'Open Project'):
						self.project.open_project_configurations_file()

			launch()

	def is_paused(self):
		if not self.sessions.has_active:
			return False
		return self.sessions.active.state == dap.Session.paused

	def is_running(self):
		if not self.sessions.has_active:
			return False
		return self.sessions.active.state == dap.Session.running

	def is_stoppable(self):
		if not self.sessions.has_active:
			return False
		return self.sessions.active.state != dap.Session.stopped

	#
	# commands
	#
	def open(self) -> None:
		self.show()

	def quit(self) -> None:
		self.dispose()

	def on_play(self) -> None:
		self.show()
		self.run_async(self._on_play())

	def on_play_no_debug(self) -> None:
		self.show()
		self.run_async(self._on_play(no_debug=True))

	async def catch_error(self, awaitabe):
		try:
			return await awaitabe()
		except core.Error as e:
			self.error(str(e))

	@core.schedule
	async def on_stop(self) -> None:
		await self.catch_error(lambda: self.sessions.active.stop())
	@core.schedule
	async def on_resume(self) -> None:
		await self.catch_error(lambda: self.sessions.active.resume())
	@core.schedule
	async def on_pause(self) -> None:
		await self.catch_error(lambda: self.sessions.active.pause())
	@core.schedule
	async def on_step_over(self) -> None:
		await self.catch_error(lambda: self.sessions.active.step_over())
	@core.schedule
	async def on_step_in(self) -> None:
		await self.catch_error(lambda: self.sessions.active.step_in())
	@core.schedule
	async def on_step_out(self) -> None:
		await self.catch_error(lambda: self.sessions.active.step_out())
	@core.schedule
	async def on_run_command(self, command: str) -> None:
		await self.catch_error(lambda: self.sessions.active.evaluate(command))

	def on_input_command(self) -> None:
		label = "Input Debugger Command"
		def run(value: str):
			if value:
				self.run_async(self.sessions.active.evaluate(value))
				self.on_input_command()

		input = ui.InputText(run, label, enable_when_active=Autocomplete.for_window(self.window))
		input.run()

	def toggle_breakpoint(self):
		self.breakpoints_provider.toggle_current_line()

	def toggle_column_breakpoint(self):
		self.breakpoints_provider.toggle_current_line_column()

	def add_function_breakpoint(self):
		self.breakpoints.function.add_command()

	def add_watch_expression(self):
		self.sessions.watch.add_command()

	def run_to_current_line(self) -> None:
		self.breakpoints_provider.run_to_current_line()

	def load_data(self):
		self.project.load_from_json(self.persistance.json.get('project', {}))
		self.breakpoints.load_from_json(self.persistance.json.get('breakpoints', {}))
		self.sessions.watch.load_json(self.persistance.json.get('watch', []))

	def save_data(self):
		self.persistance.json['project'] = self.project.into_json()
		self.persistance.json['breakpoints'] = self.breakpoints.into_json()
		self.persistance.json['watch'] = self.sessions.watch.into_json()
		self.persistance.save_to_file()

	def on_settings(self) -> None:
		def about():
			webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger#getting-started")

		def report_issue():
			webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/issues")

		values = self.change_configuration_input_items()
		values.extend([
			ui.InputListItem(lambda: ..., ""),
			ui.InputListItem(report_issue, "Report Issue"),
			ui.InputListItem(about, "About/Getting Started"),
		])

		ui.InputList(values).run()

	def on_run_task(self) -> None:
		values = []
		for task in self.project.tasks:
			def run(task=task):
				self.last_run_task = task
				self.run_task(task)

			values.append(ui.InputListItem(run, task.name))

		ui.InputList(values, 'Select task to run').run()

	def on_run_last_task(self) -> None:
		if self.last_run_task:
			self.run_task(self.last_run_task)
		else:
			self.on_run_task()

	def change_configuration_input_items(self) -> List[ui.InputListItem]:
		values = []
		for c in self.project.compounds:
			name = f'{c.name}\tcompound'
			values.append(ui.InputListItemChecked(lambda c=c: self.set_configuration(c), name, name, c == self.project.configuration_or_compound)) #type: ignore

		for c in self.project.configurations:
			name = f'{c.name}\t{c.type}'
			values.append(ui.InputListItemChecked(lambda c=c: self.set_configuration(c), name, name, c == self.project.configuration_or_compound)) #type: ignore

		if values:
			values.append(ui.InputListItem(lambda: ..., ""))

		values.append(ui.InputListItem(Adapters.add_configuration(), "Add Configuration"))
		values.append(ui.InputListItem(lambda: self.open_project_configurations_file(), "Edit Configuration File"))
		return values

	def clear_unused_terminals(self):
		for terminal in self.terminals:
			if terminal.finished:
				self.middle_panel.remove(id(terminal))
				terminal.dispose()

		self.terminals = list(filter(lambda terminal: not terminal.finished, self.terminals))

	@core.schedule
	async def run_task(self, task: dap.Task):
		variables = self.project.extract_variables()
		terminal = TerminalTask(self.window, dap.TaskExpanded(task, variables))
		self.terminals.append(terminal)

		if not terminal.background:
			self.clear_unused_terminals()
			component = ProblemsView(terminal, self.on_navigate_to_source)
			panel = TabbedPanelItem(id(terminal), component, terminal.name(), 0, show_options=lambda: terminal.show_backing_panel())

			self.middle_panel.add(panel)
			self.middle_panel.select(id(terminal))

		await terminal.wait()

	def add(self, session: dap.Session, terminal: Terminal):
		self.terminals.append(terminal)

		component = TerminalView(terminal, self.on_navigate_to_source)
		panel = TabbedPanelItem(id(terminal), component, terminal.name(), 0, show_options=lambda: terminal.show_backing_panel())

		self.middle_panel.add(panel)
		self.middle_panel.select(id(terminal))

	def external_terminal(self, session: dap.Session, request: dap.RunInTerminalRequest) -> ExternalTerminal:
		title = request.title or session.configuration.name or '?'
		env = request.env or {}
		cwd = request.cwd
		commands = request.args

		if self.project.external_terminal_kind == 'platform':
			if core.platform.osx:
				return ExternalTerminalMacDefault(title, cwd, commands, env)
			if core.platform.windows:
				return ExternalTerminalWindowsDefault(title, cwd, commands, env)
			if core.platform.linux:
				raise core.Error('default terminal for linux not implemented')

		if self.project.external_terminal_kind == 'terminus':
			return ExternalTerminalTerminus(title, cwd, commands, env)

		raise core.Error('unknown external terminal type "{}"'.format(self.project.external_terminal_kind))

	async def sessions_run_task(self, session: dap.Session, task: dap.TaskExpanded):
		await self.run_task(task)

	async def sessions_create_terminal(self, session: dap.Session, request: dap.RunInTerminalRequest) -> dap.RunInTerminalResponse:
		if request.kind == 'integrated':
			terminal = TerminalProcess(request.cwd, request.args)
			self.add(session, terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=terminal.pid())

		if request.kind == 'external':
			external_terminal = self.external_terminal(session, request)
			self.external_terminals.append(external_terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=None)

		raise dap.Error(True, "unknown terminal kind requested '{}'".format(request.kind))

	@core.schedule
	async def change_configuration(self) -> None:
		await ui.InputList(self.change_configuration_input_items(), "Add or Select Configuration").run()

	def install_adapters(self) -> None:
		self.show_console_panel()
		Adapters.install_menu(log=self).run()

	def error(self, value: str):
		self.terminal.log_error(value)

	def info(self, value: str):
		self.terminal.log_info(value)

	def refresh_phantoms(self) -> None:
		ui.reload()
