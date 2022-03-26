from __future__ import annotations
from .typecheck import *

from .import core, ui

import sublime
from functools import partial
from .import dap

from .settings import Settings
from .panel import DebuggerOutputPanel, DebuggerProtocolLogger

from .adapters_registry import AdaptersRegistry

from .debugger_console import DebuggerConsole
from .terminal_external import ExternalTerminal, ExternalTerminalTerminus, ExternalTerminalMacDefault, ExternalTerminalWindowsDefault
from .terminal_task import TerminalTask, Tasks
from .terminal_integrated import TerminalIntegrated

from .source_navigation import SourceNavigationProvider

from .views.modules import ModulesPanel
from .views.sources import SourcesPanel
from .views.callstack import CallStackPanel

from .views.debugger_panel import DebuggerPanel
from .views.variables_panel import VariablesPanel
from .views.tabbed_panel import TabbedPanel
from .views.diagnostics import DiagnosticsPanel
from .debugger import Debugger

import webbrowser

class DebuggerInterface (core.Logger):
	def __init__(self, debugger: Debugger, window: sublime.Window):
		self.disposeables: list[Any] = []
		self.window = window

		self.debugger = debugger
		self.debugger.on_session_state_updated.add(self.on_session_state_updated)
		self.debugger.on_session_active.add(self.on_session_active)
		self.debugger.on_session_added.add(self.on_session_added)
		self.debugger.on_session_removed.add(self.on_session_removed)
		self.debugger.on_session_output.add(self.on_session_output)
		self.debugger.on_session_run_terminal_requested.add(self.on_session_run_terminal_requested)
		self.debugger.on_session_run_task_requested.add(self.on_session_run_task_requested)
		self.debugger.on_info.add(self.on_info)
		self.debugger.on_error.add(self.on_error)

		self.project = debugger.project
		self.project.on_updated.add(self.on_project_or_settings_updated)

		self.source_provider = SourceNavigationProvider(self.project, self.debugger)

		self.tasks = Tasks()
		self.disposeables.extend([
			self.tasks,
			self.tasks.added.add(self.on_task_added)
		])

		self.debugger_panel = DebuggerPanel(self.debugger, self.on_navigate_to_source)
		self.debugger_panel.on_settings = lambda: self.on_settings()
		self.debugger_panel.on_start = lambda: self.start()
		self.debugger_panel.on_stop = lambda: self.stop()
		self.debugger_panel.on_pause = lambda: self.pause()
		self.debugger_panel.on_continue = lambda: self.resume()
		self.debugger_panel.on_step_over = lambda: self.step_over()
		self.debugger_panel.on_step_out = lambda: self.step_out()
		self.debugger_panel.on_step_in = lambda: self.step_in()

		# middle panels
		self.middle_panel = TabbedPanel([], 0, width_scale=0.65, width_additional=-30)

		self.console = DebuggerConsole(window)
		self.console.on_input.add(self.on_run_command)
		self.console.on_navigate.add(self.on_navigate_to_source)

		self.disposeables.extend([
			self.console,
		])

		self.terminals: list[TerminalIntegrated] = []
		self.external_terminals: dict[dap.Session, list[ExternalTerminal]] = {}

		self.callstack_panel =  CallStackPanel(self.debugger)
		self.problems_panel = DiagnosticsPanel(self.tasks, self.on_navigate_to_source)

		self.middle_panel.update([
			self.callstack_panel,
			self.problems_panel,
		])

		# right panels
		self.right_panel = TabbedPanel([], 0, width_scale=0.35, width_additional=-30)

		self.variables_panel = VariablesPanel(self.debugger)
		self.modules_panel = ModulesPanel(self.debugger)
		self.sources_panel = SourcesPanel(self.debugger, self.on_navigate_to_source)

		self.right_panel.update([
			self.variables_panel,
			self.modules_panel,
			self.sources_panel,
		])

		self.panel = DebuggerOutputPanel(window)
		self.panel.on_hidden = lambda: (self.dispose_terminals(unused_only=True), self.console.close())
		# self.panel.on_opened = lambda: self.console.show_backing_panel()

		self.disposeables.extend([
			self.panel,
		])

		self.left = ui.Phantom(self.panel.view, sublime.Region(0, 0), sublime.LAYOUT_INLINE)[
			self.debugger_panel
		]
		self.middle = ui.Phantom(self.panel.view, sublime.Region(0, 1), sublime.LAYOUT_INLINE)[
			self.middle_panel
		]
		self.right = ui.Phantom(self.panel.view, sublime.Region(0, 2), sublime.LAYOUT_INLINE)[
			self.right_panel
		]
		self.disposeables.extend([self.left, self.middle, self.right])
		
		self.on_project_or_settings_updated()

		def on_view_activated(view: sublime.View):
			if self.debugger.is_active or self.tasks.is_active():
				return
			
			window = view.window()
			if not view.element() and window and window.active_group() == 0:
				self.console.close()
				self.dispose_terminals(unused_only=True)
					

		self.disposeables.extend([
			core.on_view_activated.add(on_view_activated)
		])

	def dispose(self):
		self.dispose_terminals()
		for dispose in self.disposeables:
			dispose.dispose()

	# @core.schedule
	def start(self, no_debug: bool = False):
		async def run():
			await self.launch(no_debug=no_debug)
		
		core.schedule(run)()

	async def ensure_installed(self, configurations: list[dap.Configuration]):
		types: list[str] = []
		for configuration in configurations:
			if not configuration.type in types:
				types.append(configuration.type)

		for type in types:
			adapter_configuration = AdaptersRegistry.get(type)
			if not adapter_configuration.installed_version:
				install = 'Debug adapter with type name "{}" is not installed.\n Would you like to install it?'.format(adapter_configuration.type)
				if sublime.ok_cancel_dialog(install, 'Install'):
					await AdaptersRegistry.install(adapter_configuration.type, self)

	async def launch(self, no_debug: bool = False):
		try:
			active_configurations = self.project.active_configurations()
			if not active_configurations:
				self.error("Add or select a configuration to begin debugging")
				await self.change_configuration()

			active_configurations = self.project.active_configurations()
			if not active_configurations:
				return

			# grab variables before we open the console because the console will become the focus
			# and then things like $file would point to the console
			variables = self.project.extract_variables()

			self.dispose_terminals(unused_only=True)
			self.tasks.remove_finished()

			# clear console if there are not any currently active sessions
			if not self.debugger.sessions:
				self.console.clear()
				self.debugger.transport_log.clear()

			self.console.show()
			
			await self.ensure_installed(active_configurations)


		except Exception as e:
			core.exception()
			core.display(e)
			return

		for configuration in active_configurations:
			@core.schedule
			async def launch(configuration: dap.Configuration):
				try:
					adapter_configuration = AdaptersRegistry.get(configuration.type)
					configuration_expanded = dap.ConfigurationExpanded(configuration, variables)

					pre_debug_task = configuration_expanded.get('pre_debug_task')
					post_debug_task = configuration_expanded.get('post_debug_task')

					if pre_debug_task:
						configuration_expanded.pre_debug_task = dap.TaskExpanded(self.project.get_task(pre_debug_task), variables)

					if post_debug_task:
						configuration_expanded.post_debug_task = dap.TaskExpanded(self.project.get_task(post_debug_task), variables)						

					await self.debugger.launch(self.debugger.breakpoints, adapter_configuration, configuration_expanded, no_debug=no_debug)
				except core.Error as e:
					if sublime.ok_cancel_dialog("Error Launching Configuration\n\n{}".format(str(e)), 'Open Project'):
						self.project.open_project_configurations_file()

			launch(configuration)

	def on_project_or_settings_updated(self):
		# these settings control the size of the ui calculated in ui/layout
		settings = self.panel.view.settings()
		settings['font_size'] = Settings.ui_scale
		settings['rem_width_scale'] = Settings.ui_rem_width_scale


	def on_session_active(self, session: dap.Session):
		if not self.debugger.is_active:
			self.source_provider.clear()
			return

		active_session = self.debugger.active
		thread = active_session.selected_thread
		frame = active_session.selected_frame

		if thread and frame and frame.source:
			self.source_provider.select_source_location(dap.SourceLocation(frame.source, frame.line, frame.column), thread.stopped_reason or "Stopped")
		else:
			self.source_provider.clear()

	def on_session_added(self, sessions: dap.Session):
		self.console.show()

	def on_session_removed(self, sessions: dap.Session):
		self.console.show()

	def on_session_state_updated(self, session: dap.Session, state: dap.Session.State):
		if self.debugger.is_active and self.debugger.active != session:
			return

		if state == dap.Session.State.PAUSED or state == dap.Session.State.RUNNING:
			# if self.project.bring_window_to_front_on_pause:
			# figure out a good way to bring sublime to front
			self.middle_panel.select(self.callstack_panel)

	def on_session_output(self, session: dap.Session, event: dap.OutputEvent) -> None:
		self.console.program_output(session, event)

	async def on_session_run_task_requested(self, session: dap.Session|None, task: dap.TaskExpanded) -> None:
		await self.tasks.run(self.window, task)

	async def on_session_run_terminal_requested(self, session: dap.Session, request: dap.RunInTerminalRequestArguments) -> dap.RunInTerminalResponse:
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
			terminal = TerminalIntegrated(self.window, request.title or 'Untitled', request.args, request.cwd)
			self.terminals.append(terminal)
			return dap.RunInTerminalResponse(processId=None, shellProcessId=terminal.pid())

		raise core.Error("unknown terminal kind requested '{}'".format(request.kind))

	def dispose_terminals(self, unused_only: bool=False):
		removed_terminals: list[TerminalIntegrated] = []
		removed_sessions: list[dap.Session] = []

		for terminal in self.terminals:
			if not unused_only or terminal.closed:
				terminal.dispose()
				removed_terminals.append(terminal)

		for session, terminals in self.external_terminals.items():
			if not unused_only or session.state == dap.Session.State.STOPPED:
				removed_sessions.append(session)
				for terminal in terminals:
					terminal.dispose()

		for session in removed_sessions:
			del self.external_terminals[session]

		for terminal in removed_terminals:
			self.terminals.remove(terminal)

		self.tasks.remove_finished_terminals()

	def is_open(self):
		return self.panel.is_panel_visible()
	
	def open(self) -> None:
		self.panel.panel_show()

	def on_navigate_to_source(self, source: dap.SourceLocation):
		self.source_provider.show_source_location(source)

	def on_info(self, value: str):
		self.console.log_info(value)

	def on_error(self, value: str):
		self.console.log_error(value)

	def on_task_added(self, task: TerminalTask):
		self.middle_panel.select(self.problems_panel)

	def log(self, type: str, value: str):
		if type == 'error':
			self.console.log_error(value)
		else:
			self.console.log_info(value)

	def set_configuration(self, configuration: Union[dap.Configuration, dap.ConfigurationCompound]):
		self.project.configuration_or_compound = configuration
		self.debugger.save_data()


	async def change_configuration_input_items(self) -> list[ui.InputListItem]:
		values: list[ui.InputListItem] = []
		for c in self.project.compounds:
			name = f'{c.name}\tcompound'
			values.append(ui.InputListItemChecked(partial(self.set_configuration, c), c == self.project.configuration_or_compound, name))

		for c in self.project.configurations:
			name = f'{c.name}\t{c.type}'
			values.append(ui.InputListItemChecked(partial(self.set_configuration, c), c == self.project.configuration_or_compound, name))

		if values:
			values.append(ui.InputListItem(lambda: ..., ""))

		values.append(ui.InputListItem(await AdaptersRegistry.add_configuration(log=self), "Add Configuration"))
		values.append(ui.InputListItem(lambda: self.project.open_project_configurations_file(), "Edit Configuration File"))
		return values

	# COMMANDS
	@core.schedule
	async def stop(self, session: dap.Session|None = None) -> None:
		try: 
			if not session:
				root = self.debugger.active
				while root.parent:
					root = root.parent

				self.stop(root)
				return

			session_stop = session.stop()
			for child in session.children:
				self.stop(child)
			
			await session_stop

		except core.Error as e: self.error(f'Unable to stop: {e}')

	@core.schedule
	async def resume(self) -> None:
		try: await self.debugger.active.resume()
		except core.Error as e: self.error(f'Unable to continue: {e}')

	@core.schedule
	async def pause(self) -> None:
		try: await self.debugger.active.pause()
		except core.Error as e: self.error(f'Unable to pause: {e}')

	@core.schedule
	async def step_over(self) -> None:
		try: await self.debugger.active.step_over()
		except core.Error as e: self.error(f'Unable to step over: {e}')

	@core.schedule
	async def step_in(self) -> None:
		try: await self.debugger.active.step_in()
		except core.Error as e: self.error(f'Unable to step in: {e}')

	@core.schedule
	async def step_out(self) -> None:
		try: await self.debugger.active.step_out()
		except core.Error as e: self.error(f'Unable to step out: {e}')

	@core.schedule
	async def on_run_command(self, command: str) -> None:
		try: await self.debugger.active.evaluate(command)
		except core.Error as e: self.error(f'{e}')

	def toggle_breakpoint(self):
		file, line, _ = self.project.current_file_line_column()
		self.debugger.breakpoints.source.toggle(file, line)

	def toggle_column_breakpoint(self):
		file, line, column = self.project.current_file_line_column()
		self.debugger.breakpoints.source.toggle(file, line, column)

	def add_function_breakpoint(self):
		self.debugger.breakpoints.function.add_command()

	def add_watch_expression(self):
		self.debugger.watch.add_command()

	@core.schedule
	async def on_settings(self) -> None:
		def about():
			webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger#getting-started")

		def report_issue():
			webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/issues")

		values = await self.change_configuration_input_items()

		values.extend([
			ui.InputListItem(lambda: ..., ""),
			ui.InputListItem(report_issue, "Report Issue"),
			ui.InputListItem(about, "About/Getting Started"),
		])

		ui.InputList(values).run()


	@core.schedule
	async def change_configuration(self) -> None:
		await ui.InputList(await self.change_configuration_input_items(), "Add or Select Configuration").run()

	@core.schedule
	async def add_configuration(self) -> None:
		await (await AdaptersRegistry.add_configuration(log=self)).run()

	@core.schedule
	async def install_adapters(self) -> None:
		self.console.show()
		menu = await AdaptersRegistry.install_menu(log=self)
		await menu.run()

	def on_input_command(self) -> None:
		self.console.show()

		def run(value: str):
			# re-open
			self.on_input_command()
			if value:
				# self.show_console_panel()
				core.run(self.on_run_command(value))

		input = ui.InputText(run, 'Input Debugger Command')
		input.run()
