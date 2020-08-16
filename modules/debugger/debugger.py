from ..typecheck import *

import sublime
import sublime_plugin
import os
import subprocess
import re
import json
import types

from .. import core, ui

from .dap import types as dap

from .autocomplete import Autocomplete

from .util import get_setting
from .config import PersistedData

from .watch import Watch
from .dap import Session as DebuggerSession
from .debugger_terminals import Terminals

from .debugger_sessions import (
	DebuggerSessions,
)
from .breakpoints import (
	Breakpoints,
)

from .debugger_project import DebuggerProject
from .adapter import (
	Configuration,
	ConfigurationExpanded,
	ConfigurationCompound,
	Adapters,
)
from .terminals import (
	Terminal,
	TerminalProcess,
	TermianlDebugger,
	TerminalView,
)
from .dap import Source

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
from .debugger_log_output_panel import DebuggerLogOutputPanel

class Debugger:

	instances = {} #type: Dict[int, Debugger]
	creating = {} #type: Set[int, bool]

	@staticmethod
	def get(window: sublime.Window, run: bool = False) -> 'Optional[Debugger]':
		return Debugger.for_window(window, run)

	@staticmethod
	def should_auto_open_in_window(window: sublime.Window) -> bool:
		data = window.project_data()
		if not data:
			return False
		if "settings" not in data:
			return False
		if "debug.configurations" not in data["settings"]:
			return False
		return True

	@staticmethod
	def for_window(window: sublime.Window, create: bool = False) -> 'Optional[Debugger]':
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
			self.sessions.terminals.external_terminal_kind = self.project.external_terminal_kind
			self.configurations = self.project.configurations
			self.configuration = self.persistance.load_configuration_option(self.project.configurations, self.project.compounds)

		self.project = DebuggerProject(window)
		self.disposeables.append(self.project)
		self.project.on_updated.add(on_project_configuration_updated)
		
		self.transport_log = DebuggerLogOutputPanel(self.window)
		self.disposeables.append(self.transport_log)
		autocomplete = Autocomplete.create_for_window(window)

		def on_output(session:DebuggerSession, event: dap.OutputEvent) -> None:
			self.terminal.program_output(session, event)

		def on_terminal_added(terminal: Terminal):
			component = TerminalView(terminal, self.on_navigate_to_source)

			panel = TabbedPanelItem(id(terminal), component, terminal.name(), 0)
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
		
		self.sessions = DebuggerSessions()
		self.sessions.transport_log = self.transport_log
		self.sessions.output.add(on_output)

		self.sessions.terminals.on_terminal_added.add(on_terminal_added)
		self.sessions.terminals.on_terminal_removed.add(on_terminal_removed)
		self.disposeables.append(self.sessions)

		self.terminal = TermianlDebugger(
			on_run_command=self.on_run_command,
		)

		self.source_provider = SourceNavigationProvider(self.project, self.sessions)
		self.view_hover_provider = ViewHoverProvider(self.project, self.sessions)
		self.breakpoints_provider = BreakpointCommandsProvider(self.project, self.sessions, self.breakpoints)
		self.disposeables.extend([self.view_hover_provider, self.source_provider, self.breakpoints_provider])

		self.persistance = PersistedData(self.project.name)
		self.load_data()
		on_project_configuration_updated()


		self.terminal.log_info('Opened In Workspace: {}'.format(os.path.dirname(self.project.name)))

		def on_terminal_updated():
			# self.panels.modified(terminal_panel_item)
			...
		self.terminal.on_updated.add(on_terminal_updated)

		#left panels
		self.breakpoints_panel = BreakpointsPanel(self.breakpoints, self.on_navigate_to_source)
		self.debugger_panel = DebuggerPanel(self, self.breakpoints_panel)

		# middle panels
		self.middle_panel = TabbedPanel([], 0, width_scale=0.666, width_additional=-41)

		self.terminal_view = TerminalView(self.terminal, self.on_navigate_to_source)

		self.callstack_view =  CallStackView(self.sessions)
		self.middle_panel.update([
			TabbedPanelItem(self.terminal_view, self.terminal_view, 'Debugger Console'),
			TabbedPanelItem(self.callstack_view, self.callstack_view, 'Callstack'),
		])

		# right panels
		self.right_panel = TabbedPanel([], 0, width_scale=0.333, width_additional=-41)

		self.variables_panel = VariablesPanel(self.sessions)
		self.modules_panel = ModulesView(self.sessions)
		self.sources_panel = SourcesView(self.sessions, self.source_provider.navigate_to_source)

		self.right_panel.update([
			TabbedPanelItem(self.variables_panel, self.variables_panel, 'Variables'),
			TabbedPanelItem(self.modules_panel, self.modules_panel, 'Modules'),
			TabbedPanelItem(self.sources_panel, self.sources_panel, 'Sources'),
		])

		self.update_modules_visibility()
		self.update_sources_visibility()

		# phantoms
		phantom_location = self.project.panel_phantom_location()
		phantom_view = self.project.panel_phantom_view()

		self.left = ui.Phantom(self.debugger_panel, phantom_view, sublime.Region(phantom_location, phantom_location), sublime.LAYOUT_INLINE)
		self.middle = ui.Phantom(self.middle_panel, phantom_view, sublime.Region(phantom_location + 0, phantom_location + 1), sublime.LAYOUT_INLINE)
		self.right = ui.Phantom(self.right_panel, phantom_view, sublime.Region(phantom_location + 0, phantom_location + 2), sublime.LAYOUT_INLINE)
		self.disposeables.extend([self.left, self.middle, self.right])

		self.sessions.on_updated_modules.add(lambda s: self.update_modules_visibility())
		self.sessions.on_updated_sources.add(lambda s: self.update_sources_visibility())
		self.sessions.on_removed_session.add(self.on_session_removed)
		self.sessions.updated.add(self.on_session_state_changed)
		self.sessions.on_selected.add(self.on_session_selection_changed)

	def on_session_removed(self, session: DebuggerSession):
		self.update_sources_visibility()
		self.update_modules_visibility()

	def on_session_selection_changed(self, session: DebuggerSession):
		if not self.sessions.has_active:
			self.source_provider.clear()
			return

		active_session = self.sessions.active
		thread = active_session.selected_thread
		frame = active_session.selected_frame

		if thread and frame and frame.source:
			self.source_provider.select_source_location(Source(frame.source, frame.line, frame.column), thread.stopped_reason or "Stopped")
		else:
			self.source_provider.clear()

	def on_session_state_changed(self, session: DebuggerSession, state):
		if state == DebuggerSession.stopped:
			if self.sessions or session.stopped_reason == DebuggerSession.stopped_reason_build_failed:
				... # leave build results open or there is still a running session
			else:
				self.show_console_panel()

		elif state == DebuggerSession.running:
			self.show_console_panel()

		elif state == DebuggerSession.paused:
			if self.project.bring_window_to_front_on_pause:
				# is there a better way to bring sublime to the front??
				# this probably doesn't work for most people. subl needs to be in PATH
				# ignore any errors
				try:
					subprocess.call(["subl"])
				except Exception:
					pass

			self.show_call_stack_panel()

		elif state == DebuggerSession.stopping or state == DebuggerSession.starting:
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
		self.project.panel_show()

	def show_console_panel(self) -> None:
		self.middle_panel.select(self.terminal_view)

	def show_call_stack_panel(self) -> None:
		self.middle_panel.select(self.callstack_view)

	def changeConfiguration(self, configuration: Union[Configuration, ConfigurationCompound]):
		self.configuration = configuration
		self.persistance.save_configuration_option(configuration)

	def dispose(self) -> None:
		self.save_data()
		for d in self.disposeables:
			d.dispose()

		del Debugger.instances[self.window.id()]

	def run_async(self, awaitable: Awaitable[core.T]):
		def on_error(e: Exception) -> None:
			self.terminal.log_error(str(e))
		core.run(awaitable, on_error=on_error)

	def on_navigate_to_source(self, source: Source):
		self.source_provider.show_source_location(source)

	async def _on_play(self, no_debug=False) -> None:
		self.show_console_panel()
		self.sessions.terminals.clear_unused()
		self.terminal.clear()
		self.terminal.log_info('Console cleared...')
		try:
			if not self.configuration:
				self.terminal.log_error("Add or select a configuration to begin debugging")
				Adapters.select_configuration(self).run()
				return

			if isinstance(self.configuration, ConfigurationCompound):
				configurations = []
				for configuration_name in self.configuration.configurations:
					configuration = None
					for c in self.configurations:
						if c.name == configuration_name:
							configuration = c
							break

					if configuration:
						configurations.append(configuration)
					else:
						raise core.Error(f'Unable to find configuration with name {configuration_name} while evaluating compound {self.configuration.name}')

			elif isinstance(self.configuration, Configuration):
				configurations = [self.configuration]
			else:
				raise core.Error('unreachable')

		except Exception as e:
			core.log_exception()
			core.display(e)
			return

		variables = self.project.extract_variables()

		for configuration in configurations:
			@core.schedule
			async def launch():
				try:
					adapter_configuration = Adapters.get(configuration.type)
					configuration_expanded = ConfigurationExpanded(configuration, variables)
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
		return self.sessions.active.state == DebuggerSession.paused

	def is_running(self):
		if not self.sessions.has_active:
			return False
		return self.sessions.active.state == DebuggerSession.running

	def is_stoppable(self):
		if not self.sessions.has_active:
			return False
		return self.sessions.active.state != DebuggerSession.stopped

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
		self.breakpoints.load_from_json(self.persistance.json.get('breakpoints', {}))
		self.sessions.watch.load_json(self.persistance.json.get('watch', []))

	def save_data(self):
		self.persistance.json['breakpoints'] = self.breakpoints.into_json()
		self.persistance.json['watch'] = self.sessions.watch.into_json()
		self.persistance.save_to_file()

	def on_settings(self) -> None:
		import webbrowser
		def about():
			webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/blob/master/docs/setup.md")
		
		def report_issue():
			webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/issues")

		values = Adapters.select_configuration(self).values
		values.extend([
			ui.InputListItem(lambda: ..., ""),
			ui.InputListItem(report_issue, "Report Issue"),
			ui.InputListItem(about, "About/Getting Started"),
		])

		ui.InputList(values).run()

	def install_adapters(self) -> None:
		self.show_console_panel()
		Adapters.install_menu(log=self).run()

	def change_configuration(self) -> None:
		Adapters.select_configuration(self).run()

	def error(self, value: str):
		self.terminal.log_error(value)

	def info(self, value: str):
		self.terminal.log_info(value)

	def refresh_phantoms(self) -> None:
		ui.reload()
