from ..typecheck import *

import sublime
import sublime_plugin
import os
import subprocess
import re
import json
import types

from .. import core, ui, dap

from .autocomplete import Autocomplete

from .util import WindowSettingsCallback, get_setting
from .config import PersistedData

from .debugger_session import (
	DebuggerSession,
	Modules,
	Sources,
	Variables,
	Watch,
	Threads,
	Terminals
)
from .debugger_project import (
	DebuggerProject
)
from .breakpoints import (
	Breakpoints,
)
from .adapter import (
	Configuration,
	ConfigurationExpanded,
	Adapters,
)
from .output_panel import OutputPhantomsPanel

from .terminals import (
	Terminal,
	TerminalProcess,
	TermianlDebugger,
	TerminalView,
)
from .watch import WatchView

from .view_hover import ViewHoverProvider
from .view_selected_source import ViewSelectedSourceProvider
from .breakpoint_commands import BreakpointCommandsProvider

from .views.modules import ModulesView
from .views.sources import SourcesView
from .views.callstack import CallStackView

from .views.debugger_panel import DebuggerPanel, STOPPED, PAUSED, RUNNING, LOADING
from .views.breakpoints_panel import BreakpointsPanel
from .views.variables_panel import VariablesPanel
from .views.tabbed_panel import Panels, TabbedPanel, TabbedPanelItem
from .views.selected_line import SelectedLine



class Debugger:

	instances = {} #type: Dict[int, Debugger]

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
		instance = Debugger.instances.get(window.id())
		if not instance and create:
			try:
				main = Debugger(window)
				Debugger.instances[window.id()] = main
				return main
			except dap.Error as e:
				core.log_exception()
		if instance and create:
			instance.show()
		return instance

	def refresh_phantoms(self) -> None:
		ui.reload()

	def __init__(self, window: sublime.Window) -> None:

		# ensure we are being run inside a sublime project
		# if not prompt the user to create one
		while True:
			data = window.project_data()
			project_name = window.project_file_name()
			while not data or not project_name:
				r = sublime.ok_cancel_dialog("Debugger requires a sublime project. Would you like to create a new sublime project?", "Save Project As...")
				if r:
					window.run_command('save_project_and_workspace_as')
				else:
					raise core.Error("Debugger must be run inside a sublime project")

			# ensure we have debug configurations added to the project file
			data.setdefault('settings', {}).setdefault('debug.configurations', [])
			window.set_project_data(data)
			break

		self.window = window
		self.disposeables = [] #type: List[Any]

		def on_project_configuration_updated():
			print('on_project_configuration_updated')
			self.terminals.external_terminal_kind = self.project.external_terminal_kind
			self.configurations = self.project.configurations
			self.configuration = self.persistance.load_configuration_option(self.configurations)

		self.project = DebuggerProject(window)
		self.disposeables.append(self.project)
		self.project.on_updated.add(on_project_configuration_updated)
		

		autocomplete = Autocomplete.create_for_window(window)

		def on_state_changed(state: int) -> None:
			if state == DebuggerSession.stopped:
				self.debugger_panel.setState(STOPPED)
				if self.debugger.stopped_reason != DebuggerSession.stopped_reason_build_failed:
					self.show_console_panel()

			elif state == DebuggerSession.running:
				self.debugger_panel.setState(RUNNING)
			elif state == DebuggerSession.paused:
				self.debugger_panel.setState(PAUSED)

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
				self.debugger_panel.setState(LOADING)

		def on_selected_frame(frame: Optional[dap.StackFrame]) -> None:
			if frame and frame.source:
				thread = self.debugger.callstack.selected_thread
				assert thread
				self.source_provider.select(frame.source, frame.line, thread.stopped_reason or "Stopped")
			else:
				self.source_provider.clear()

		def on_output(event: dap.OutputEvent) -> None:
			self.terminal.program_output(self.debugger.adapter, event)

		def on_terminal_added(terminal: Terminal):
			component = TerminalView(terminal, self.on_navigate_to_source)

			panel = TabbedPanelItem(id(terminal), component, terminal.name(), 0, component.action_buttons())
			def on_modified():
				self.panels.modified(panel)

			terminal.on_updated.add(on_modified)

			self.panels.add([panel])
			self.panels.show(id(terminal))

		def on_terminal_removed(terminal: Terminal):
			self.panels.remove(id(terminal))

		self.modules = Modules()
		self.sources = Sources()
		self.variables = Variables()
		self.threads = Threads()
		self.watch = Watch()
		self.breakpoints = Breakpoints()
		self.terminals = Terminals()
		self.terminals.on_terminal_added.add(on_terminal_added)
		self.terminals.on_terminal_removed.add(on_terminal_removed)

		self.debugger = DebuggerSession(
			breakpoints=self.breakpoints,
			modules=self.modules,
			sources=self.sources,
			threads=self.threads,
			watch=self.watch,
			variables=self.variables,
			terminals=self.terminals,
			on_state_changed=on_state_changed,
			on_output=on_output,
			on_selected_frame=on_selected_frame)

		self.breakpoints_panel = BreakpointsPanel(self.debugger.breakpoints)
		self.debugger_panel = DebuggerPanel(self, self.breakpoints_panel)
		self.variables_panel = VariablesPanel(self.debugger.variables, self.debugger.watch)
		self.terminal = TermianlDebugger(
			self.debugger,
			on_run_command=self.on_run_command,
		)

		self.source_provider = ViewSelectedSourceProvider(self.project, self.debugger)
		self.view_hover_provider = ViewHoverProvider(self.project, self.debugger)
		self.breakpoints_provider = BreakpointCommandsProvider(self.project, self.debugger, self.debugger.breakpoints)


		self.persistance = PersistedData(project_name)
		self.load_data()
		on_project_configuration_updated()

		phantom_location = self.project.panel_phantom_location()
		phantom_view = self.project.panel_phantom_view()

		terminal_component = TerminalView(self.terminal, self.on_navigate_to_source)
		terminal_panel_item = TabbedPanelItem(id(self.terminal), terminal_component, self.terminal.name(), 0)
		callstack_panel_item = TabbedPanelItem(id(self.debugger.callstack), CallStackView(self.debugger), "Call Stack", 0)

		variables_panel_item = TabbedPanelItem(id(self.variables_panel), self.variables_panel, "Variables", 1)
		modules_panel = TabbedPanelItem(id(self.debugger.modules), ModulesView(self.debugger.modules), "Modules", 1)
		sources_panel = TabbedPanelItem(id(self.debugger.sources), SourcesView(self.debugger.sources, self.source_provider.navigate), "Sources", 1)

		self.terminal.log_info('Opened In Workspace: {}'.format(os.path.dirname(project_name)))

		self.disposeables.extend([
			ui.Phantom(self.debugger_panel, phantom_view, sublime.Region(phantom_location, phantom_location), sublime.LAYOUT_INLINE),
		])
		self.panels = Panels(phantom_view, phantom_location + 1, 3)
		self.panels.add([
			terminal_panel_item,
			callstack_panel_item,
			variables_panel_item,
			modules_panel,
			sources_panel
		])
		def on_terminal_updated():
			 self.panels.modified(terminal_panel_item)
		self.terminal.on_updated.add(on_terminal_updated)

		self.disposeables.append(self.view_hover_provider)
		self.disposeables.append(self.source_provider)
		self.disposeables.append(self.breakpoints_provider)

	def show(self) -> None:
		self.project.panel_show()

	def show_console_panel(self) -> None:
		self.panels.show(id(self.terminal))

	def show_call_stack_panel(self) -> None:
		self.panels.show(id(self.debugger.callstack))

	def changeConfiguration(self, configuration: Configuration):
		self.configuration = configuration
		self.persistance.save_configuration_option(configuration)

	def dispose(self) -> None:
		self.save_data()
		for d in self.disposeables:
			d.dispose()

		if self.debugger:
			self.debugger.dispose()
		del Debugger.instances[self.window.id()]

	def run_async(self, awaitable: Awaitable[core.T]):
		def on_error(e: Exception) -> None:
			self.terminal.log_error(str(e))
		core.run(awaitable, on_error=on_error)

	def on_navigate_to_source(self, source: dap.Source, line: Optional[int]):
		self.source_provider.navigate(source, line or 1)

	async def _on_play(self, no_debug=False) -> None:
		self.show_console_panel()
		self.terminal.clear()
		self.terminal.log_info('Console cleared...')
		try:
			if not self.configuration:
				self.terminal.log_error("Add or select a configuration to begin debugging")
				Adapters.select_configuration(self).run()
				return

			configuration = self.configuration
			adapter_configuration = Adapters.get(configuration.type)

		except Exception as e:
			core.log_exception()
			core.display(e)
			return

		variables = self.project.extract_variables()
		configuration_expanded = ConfigurationExpanded(configuration, variables)

		try:
			await self.debugger.launch(adapter_configuration, configuration_expanded, no_debug=no_debug)
		except core.Error as e:
			if sublime.ok_cancel_dialog("Error Launching Configuration\n\n{}".format(str(e)), 'Open Project'):
				project_name = self.window.project_file_name()
				view = await core.sublime_open_file_async(self.window, project_name)
				region = view.find('''"\s*debug.configurations''', 0)
				if region:
					view.show_at_center(region)


	def is_paused(self):
		return self.debugger.state == DebuggerSession.paused

	def is_running(self):
		return self.debugger.state == DebuggerSession.running

	def is_stoppable(self):
		return self.debugger.state != DebuggerSession.stopped

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

	def on_stop(self) -> None:
		self.run_async(self.debugger.stop())

	def on_resume(self) -> None:
		self.run_async(self.debugger.resume())

	def on_pause(self) -> None:
		self.run_async(self.debugger.pause())

	def on_step_over(self) -> None:
		self.run_async(self.debugger.step_over())

	def on_step_in(self) -> None:
		self.run_async(self.debugger.step_in())

	def on_step_out(self) -> None:
		self.run_async(self.debugger.step_out())

	def on_run_command(self, command: str) -> None:
		self.run_async(self.debugger.evaluate(command))

	def on_input_command(self) -> None:
		label = "Input Debugger Command"
		def run(value: str):
			if value:
				self.run_async(self.debugger.evaluate(value))
				self.on_input_command()

		input = ui.InputText(run, label, enable_when_active=Autocomplete.for_window(self.window))
		input.run()

	def toggle_breakpoint(self):
		self.breakpoints_provider.toggle_current_line()

	def toggle_column_breakpoint(self):
		self.breakpoints_provider.toggle_current_line_column()

	def add_function_breakpoint(self):
		self.debugger.breakpoints.function.add_command()

	def add_watch_expression(self):
		self.debugger.watch.add_command()

	def run_to_current_line(self) -> None:
		self.breakpoints_provider.run_to_current_line()

	def load_data(self):
		self.debugger.breakpoints.load_from_json(self.persistance.json.get('breakpoints', {}))
		self.debugger.watch.load_json(self.persistance.json.get('watch', []))

	def save_data(self):
		self.persistance.json['breakpoints'] = self.debugger.breakpoints.into_json()
		self.persistance.json['watch'] = self.debugger.watch.into_json()
		self.persistance.save_to_file()

	def on_settings(self) -> None:
		import webbrowser
		def about():
			webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/blob/master/docs/setup.md")
		
		def report_issue():
			webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/issues")

		values = Adapters.select_configuration(debugger).values
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
