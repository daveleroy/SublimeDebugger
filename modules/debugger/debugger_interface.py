from ..typecheck import *

import sublime
import sublime_plugin
import os
import subprocess
import re
import json
import types

from .. import core, ui, dap

from ..components.variable_component import VariableStateful, VariableStatefulComponent, Variable
from ..components.debugger_panel import DebuggerPanel, DebuggerPanelCallbacks, STOPPED, PAUSED, RUNNING, LOADING
from ..components.breakpoints_panel import BreakpointsPanel
from ..components.callstack_panel import CallStackPanel
from ..components.variables_panel import VariablesPanel
from ..components.pages_panel import TabbedPanel
from ..components.selected_line import SelectedLine

from ..commands.commands import Autocomplete, AutoCompleteTextInputHandler
from ..commands import breakpoint_menus
from ..commands import select_configuration

from .util import WindowSettingsCallback, get_setting
from .config import PersistedData

from ..debugger.debugger import (
	DebuggerStateful,
)

from .debugger_project import (
	DebuggerProject
)

from .breakpoints import (
	Breakpoints, 
)

from .adapter_configuration import (
	Configuration,
	ConfigurationExpanded,
	AdapterConfiguration
)

from .output_panel import OutputPhantomsPanel

from .terminal import TerminalComponent
from .debugger_terminal import DebuggerTerminal
from .. components.pages_panel import TabbedPanelItem

from .view_hover import ViewHoverProvider
from .view_selected_source import ViewSelectedSourceProvider
from .breakpoint_commands import BreakpointCommandsProvider

class Panels:
	def __init__(self, view: sublime.View, phantom_location: int, columns: int):
		self.panels = []
		self.pages = []
		self.columns = columns
		for i in range(0, columns):
			pages = TabbedPanel([], 0)
			self.pages.append(pages)
			phantom = ui.Phantom(pages, view, sublime.Region(phantom_location, phantom_location + i), sublime.LAYOUT_INLINE)

	def add(self, panels: [TabbedPanelItem]):
		self.panels.extend(panels)
		self.layout()

	def modified(self, panel: TabbedPanelItem):
		column = panel.column
		row = panel.row
		if row >= 0 and column >= 0:
			self.pages[column].modified(row)

	def remove(self, id: int):
		for item in self.panels:
			if item.id == id:
				self.panels.remove(item)
				self.layout()
				return

	def show(self, id: int):
		for panel in self.panels:
			if panel.id == id:
				column = panel.column
				row = panel.row
				self.pages[column].show(row)

	def layout(self):
		items = []
		for i in range(0, self.columns): 
			items.append([])

		for panel in self.panels:
			panel.column = panel.index % self.columns
			panel.row = len(items[panel.column])
			items[panel.column].append(panel)

		for i in range(0, self.columns): 
			self.pages[i].update(items[i])

class DebuggerInterface (DebuggerPanelCallbacks):
	instances = {} #type: Dict[int, DebuggerInterface]

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
	def for_window(window: sublime.Window, create: bool = False) -> 'Optional[DebuggerInterface]':
		instance = DebuggerInterface.instances.get(window.id())
		if not instance and create:
			try:
				main = DebuggerInterface(window)
				DebuggerInterface.instances[window.id()] = main
				return main
			except dap.Error as e:
				core.log_exception()
		if create:
			instance.show()
		return instance

	@staticmethod
	def debuggerForWindow(window: sublime.Window) -> Optional[DebuggerStateful]:
		main = DebuggerInterface.for_window(window)
		if main:
			return main.debugger
		return None

	def refresh_phantoms(self) -> None:
		ui.reload()

	def open_repl_console(self) -> None:
		label = "input debugger command"
		input = AutoCompleteTextInputHandler(label)
		def run(**args):
			expression = args['text']
			self.run_async(self.debugger.evaluate(expression))

		# just re run the same command right away to avoid flicker
		def run_not_main(**args):
			ui.run_input_command(input, run, run_not_main=run_not_main)

		ui.run_input_command(input, run, run_not_main=run_not_main)		

	@core.require_main_thread
	def __init__(self, window: sublime.Window) -> None:

		# ensure we are being run inside a sublime project
		# if not prompt the user to create one
		while True:
			data = window.project_data()
			project_name = window.project_file_name()
			if not data or not project_name:
				r = sublime.ok_cancel_dialog("Debugger requires a sublime project. Would you like to create a new sublime project?", "Save Project As...")
				if r:
					window.run_command('save_project_and_workspace_as')
				else:
					raise Error(True, "Debugger must be run inside a sublime project")

			# ensure we have debug configurations added to the project file
			data.setdefault('settings', {}).setdefault('debug.configurations', [])
			window.set_project_data(data)
			break
		self.project = DebuggerProject(window)

		autocomplete = Autocomplete.create_for_window(window)

		self.window = window
		self.disposeables = [] #type: List[Any]
		
		self.breakpoints = Breakpoints();
		self.variables_panel = VariablesPanel(self.breakpoints)
		self.callstack_panel = CallStackPanel()
		self.breakpoints_panel = BreakpointsPanel(self.breakpoints)
		self.debugger_panel = DebuggerPanel(self, self.breakpoints_panel)

		def on_state_changed(state: int) -> None:
			if state == DebuggerStateful.stopped:
				self.breakpoints.clear_session_data()
				self.debugger_panel.setState(STOPPED)
				self.show_console_panel()
			elif state == DebuggerStateful.running:
				self.debugger_panel.setState(RUNNING)
			elif state == DebuggerStateful.paused:
				self.debugger_panel.setState(PAUSED)

				if get_setting(self.view, 'bring_window_to_front_on_pause', False):
					# is there a better way to bring sublime to the front??
					# this probably doesn't work for most people. subl needs to be in PATH
					file = self.window.active_view().file_name()
					if file:
						# ignore any errors
						try:
							subprocess.call(["subl", file])
						except Exception:
							pass

				self.show_call_stack_panel()
			elif state == DebuggerStateful.stopping or state == DebuggerStateful.starting:
				self.debugger_panel.setState(LOADING)

		def on_scopes(scopes: List[dap.Scope]) -> None:
			self.variables_panel.set_scopes(scopes)

		def on_selected_frame(thread: Optional[dap.Thread], frame: Optional[dap.StackFrame]) -> None:
			if frame and thread and frame.source:
				self.source_provider.select(frame.source, frame.line, thread.stopped_text)
			else:
				self.source_provider.clear()

		def on_output(event: dap.OutputEvent) -> None:
			self.terminal.program_output(self.debugger.adapter, event)

		def on_threads_stateful(threads: Any):
			self.callstack_panel.update(self.debugger, threads)


		from .diff import DiffCollection
		from .terminal import Terminal
		def on_terminal_added(terminal: Terminal):
			component = TerminalComponent(terminal)

			panel = TabbedPanelItem(id(terminal), component, terminal.name(), 0, component.action_buttons())
			def on_modified():
				self.panels.modified(panel)

			terminal.on_updated.add(on_modified)

			self.panels.add([panel])

		def on_terminal_removed(terminal: Terminal):
			self.panels.remove(id(terminal))

		terminals = DiffCollection(on_terminal_added, on_terminal_removed)
		
		def on_terminals(list: Any):
			terminals.update(list)

		self.debugger = DebuggerStateful(
			self.breakpoints,
			on_state_changed=on_state_changed,
			on_scopes=on_scopes,
			on_output=on_output,
			on_selected_frame=on_selected_frame,
			on_threads_stateful=on_threads_stateful,
			on_terminals=on_terminals)

		self.panel = OutputPhantomsPanel(window, 'Debugger')
		self.panel.show()
		self.view = self.panel.view #type: sublime.View

		self.persistance = PersistedData(project_name)
		self.load_data()
		self.load_settings_and_configurations()

		self.disposeables.extend([
			self.panel,
			ui.view_gutter_hovered.add(self.on_gutter_hovered),
		])


		self.disposeables.append(WindowSettingsCallback(self.window, self.on_settings_updated))

		phantom_location = self.panel.phantom_location()
		phantom_view = self.panel.phantom_view()
		self.disposeables.extend([
			ui.Phantom(self.debugger_panel, phantom_view, sublime.Region(phantom_location, phantom_location + 0), sublime.LAYOUT_INLINE),
		])

		callstack_panel_item = TabbedPanelItem(id(self.callstack_panel), self.callstack_panel, "Call Stack", 0)
		variables_panel_item = TabbedPanelItem(id(self.variables_panel), self.variables_panel, "Variables", 1)

		self.terminal = DebuggerTerminal(
			on_run_command=self.on_run_command, 
			on_clicked_source=self.on_navigate_to_source
		)
		terminal_component = TerminalComponent(self.terminal)
		terminal_panel_item = TabbedPanelItem(id(self.terminal), terminal_component, self.terminal.name(), 0)

		self.terminal.log_info('Opened In Workspace: {}'.format(os.path.dirname(project_name)))


		self.panels = Panels(phantom_view, phantom_location + 1, 3)
		self.panels.add([
			callstack_panel_item,
			variables_panel_item,
			terminal_panel_item
		])

		view_hover = ViewHoverProvider(self.project, self.debugger)
		self.disposeables.append(view_hover)

		self.source_provider = ViewSelectedSourceProvider(self.project, self.debugger)
		self.disposeables.append(self.source_provider)

		self.breakpoints_provider = BreakpointCommandsProvider(self.project, self.debugger, self.breakpoints)
		self.disposeables.append(self.breakpoints_provider)

	def load_settings_and_configurations(self) -> None:

		# logging settings
		core.log_configure(
			log_info=get_setting(self.window.active_view(), 'log_info', False),
			log_errors=get_setting(self.window.active_view(), 'log_errors', True),
			log_exceptions=get_setting(self.window.active_view(), 'log_exceptions', True),
		)

		# configuration settings
		variables = self.project.extract_variables()
		adapters = {}

		def load_adapter(adapter_name, adapter_json):
			adapter_json = sublime.expand_variables(adapter_json, variables)

			# if its a string then it points to a json file with configuration in it
			# otherwise it is the configuration
			try:
				if isinstance(adapter_json, str):
					with open(adapter_json) as json_data:
						adapter_json = json.load(json_data,)
						adapter_json = sublime.expand_variables(adapter_json, variables)
			except Exception as e:
				core.display('Failed when opening debug adapter configuration file {}'.format(e))
				raise e

			try:
				adapter = AdapterConfiguration.from_json(adapter_name, adapter_json)
				adapters[adapter.type] = adapter
			except Exception as e:
				core.display('There was an error creating a AdapterConfiguration {}'.format(e))

		for adapter_name, adapter_json in get_setting(self.window.active_view(), 'adapters', {}).items():
			load_adapter(adapter_name, adapter_json)

		for adapter_name, adapter_json in get_setting(self.window.active_view(), 'adapters_custom', {}).items():
			load_adapter(adapter_name, adapter_json)

		configurations = []
		configurations_json = [] #type: list
		data = self.window.project_data()
		if data:
			configurations_json = data.setdefault('settings', {}).setdefault('debug.configurations', [])

		for index, configuration_json in enumerate(configurations_json):
			configuration = Configuration.from_json(configuration_json)
			configuration.index = index
			configurations.append(configuration)

		self.adapters = adapters
		self.configurations = configurations
		self.configuration = self.persistance.load_configuration_option(configurations)

		self.panel.ui_scale = get_setting(self.view, 'ui_scale', 12)

	def on_settings_updated(self) -> None:
		print('Settings were udpdated: reloading configuations')
		self.load_settings_and_configurations()

	def show(self) -> None:
		self.panel.show()

	def changeConfiguration(self, configuration: Configuration):
		self.configuration = configuration
		self.persistance.save_configuration_option(configuration)

	def on_gutter_hovered(self, event: ui.GutterEvent) -> None:
		if not self.project.is_source_file(event.view):
			return

		file = event.view.file_name()
		line = event.line + 1
		self.breakpoints_provider.edit_breakpoints_at_line(file, line)

	def dispose(self) -> None:
		self.save_data()
		for d in self.disposeables:
			d.dispose()

		self.breakpoints.dispose()
		if self.debugger:
			self.debugger.dispose()
		del DebuggerInterface.instances[self.window.id()]

	def show_console_panel(self) -> None:
		self.panels.show(id(self.terminal))

	def show_call_stack_panel(self) -> None:
		self.panels.show(id(self.callstack_panel))

	def run_async(self, awaitable: core.awaitable[None]):
		def on_error(e: Exception) -> None:
			self.terminal.log_error(str(e))
		core.run(awaitable, on_error=on_error)

	def on_navigate_to_source(self, source: dap.Source, line: int):
		self.source_provider.navigate(source, line)

	def command(enabled=None, disabled=None):
		def wrap(f):
			@property
			def wrapper(self):
				class command:
					def __init__(self, debugger, enabled, disabled, f):
						self.f = f
						self.debugger = debugger
						self._enabled = enabled
						self._disabled = disabled

					def __call__(self, *args, **kw):
						return self.f(self.debugger)

					def enabled(self):
						if self._enabled is not None:
							if self.debugger.debugger.state != self._enabled:
								return False
						if self._disabled is not None:
							if self.debugger.debugger.state == self._disabled:
								return False

						return True

				return command(self, enabled, disabled, f)
			return wrapper
		return wrap

	@command()
	def on_play(self) -> None:
		self.panel.show()

		@core.async
		def on_play_async() -> core.awaitable[None]:
			self.show_console_panel()
			self.terminal.clear()
			self.terminal.log_info('Console cleared...')
			try:
				if not self.configuration:
					self.terminal.log_error("Add or select a configuration to begin debugging")
					select_configuration.run(self)
					return

				configuration = self.configuration

				adapter_configuration = self.adapters.get(configuration.type)
				if not adapter_configuration:
					raise Exception('Unable to find debug adapter with the type name "{}"'.format(configuration.type))

			except Exception as e:
				core.log_exception()
				core.display(e)
				return

			variables = self.project.extract_variables()
			configuration_expanded = ConfigurationExpanded(configuration, variables)
			yield from self.debugger.launch(adapter_configuration, configuration_expanded)

		self.run_async(on_play_async())

	@command(disabled=DebuggerStateful.stopped)
	def on_stop(self) -> None:
		self.run_async(self.debugger.stop())

	@command(enabled=DebuggerStateful.paused)
	def on_resume(self) -> None:
		self.run_async(self.debugger.resume())

	@command(enabled=DebuggerStateful.running)
	def on_pause(self) -> None:
		self.run_async(self.debugger.pause())

	@command(enabled=DebuggerStateful.paused)
	def on_step_over(self) -> None:
		self.run_async(self.debugger.step_over())

	@command(enabled=DebuggerStateful.paused)
	def on_step_in(self) -> None:
		self.run_async(self.debugger.step_in())

	@command(enabled=DebuggerStateful.paused)
	def on_step_out(self) -> None:
		self.run_async(self.debugger.step_out())

	@command(disabled=DebuggerStateful.stopped)
	def on_run_command(self, command: str) -> None:
		self.run_async(self.debugger.evaluate(command))

	@command()
	def toggle_breakpoint(self):
		self.breakpoints_provider.toggle_current_line()
	
	@command()
	def toggle_column_breakpoint(self):
		self.breakpoints_provider.toggle_current_line_column()

	@command()
	def add_function_breakpoint(self):
		self.breakpoints.function.add_command()
		self.breakpoints.load_from_json(self.persistance.json.get('breakpoints', {}))
		self.persistance.json['breakpoints'] = self.breakpoints.into_json()
		self.persistance.save_to_file()

	@command(enabled=DebuggerStateful.paused)
	def run_to_current_line(self) -> None:
		self.breakpoints_provider.run_to_current_line()
