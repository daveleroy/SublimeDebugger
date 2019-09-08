from ..typecheck import *

import sublime
import sublime_plugin
import os
import subprocess
import re
import json

from .. import ui
from .. import core

from ..components.variable_component import VariableStateful, VariableStatefulComponent, Variable
from ..components.debugger_panel import DebuggerPanel, DebuggerPanelCallbacks, STOPPED, PAUSED, RUNNING, LOADING
from ..components.breakpoints_panel import BreakpointsPanel, show_breakpoint_options
from ..components.callstack_panel import CallStackPanel
from ..components.variables_panel import VariablesPanel
from ..components.pages_panel import TabbedPanel
from ..components.selected_line import SelectedLine

from ..commands.commands import Autocomplete, AutoCompleteTextInputHandler
from ..commands import breakpoint_menus
from ..commands import select_configuration

from .util import WindowSettingsCallback, get_setting, extract_variables
from .config import PersistedData

from ..debugger.debugger import (
	DebuggerStateful,
	OutputEvent,
	StackFrame,
	Scope,
	Thread,
	EvaluateResponse,
	DebugAdapterClient,
	Error,
	Source
)
from .breakpoints import (
	Breakpoints, 
	Breakpoint, 
	Filter
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
			except Error as e:
				core.log_exception()
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

		autocomplete = Autocomplete.create_for_window(window)

		self.input_open = False
		self.window = window
		self.disposeables = [] #type: List[Any]
		self.breakpoints = Breakpoints()

		self.variables_panel = VariablesPanel()
		self.callstack_panel = CallStackPanel()
		self.breakpoints_panel = BreakpointsPanel(self.breakpoints, self.onSelectedBreakpoint)

		def on_breakpoint_more():
			show_breakpoint_options(self.breakpoints)


		self.debugger_panel = DebuggerPanel(self, self.breakpoints_panel)

		self.selected_frame_line = None #type: Optional[SelectedLine]
		self.selected_frame_generated_view = None #type: Optional[sublime.View]

		def on_state_changed(state: int) -> None:
			if state == DebuggerStateful.stopped:
				self.breakpoints.clear_breakpoint_results()
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

		def on_scopes(scopes: List[Scope]) -> None:
			self.variables_panel.set_scopes(scopes)

		def on_selected_frame(thread: Optional[Thread], frame: Optional[StackFrame]) -> None:
			if frame and thread:
				self.run_async(self.navigate_to_frame(thread, frame))
			else:
				self.dispose_selected_frame()

		def on_output(event: OutputEvent) -> None:
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
		self.persistance.load_breakpoints(self.breakpoints)

		self.load_configurations()



		print('Creating a window: h')

		self.disposeables.extend([
			self.panel,
			ui.view_gutter_hovered.add(self.on_gutter_hovered),
			ui.view_text_hovered.add(self.on_text_hovered),
			self.breakpoints.onSelectedBreakpoint.add(self.onSelectedBreakpoint)
		])


		self.disposeables.append(WindowSettingsCallback(self.window, self.on_settings_updated))

		phantom_location = self.panel.phantom_location()
		self.disposeables.extend([
			ui.Phantom(self.debugger_panel, self.view, sublime.Region(phantom_location, phantom_location + 0), sublime.LAYOUT_INLINE),
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


		self.panels = Panels(self.view, phantom_location + 1, 3)
		self.panels.add([
			callstack_panel_item,
			variables_panel_item,
			terminal_panel_item
		])

	def update_panels(self):
		pass

	def load_configurations(self) -> None:
		variables = extract_variables(self.window)
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

		if self.configuration:
			self.debugger_panel.set_name(self.configuration.name)
		else:
			self.debugger_panel.set_name('select config')

		assert self.view
		self.view.settings().set('font_size', get_setting(self.view, 'ui_scale', 12))

	def on_settings_updated(self) -> None:
		print('Settings were udpdated: reloading configuations')
		self.load_configurations()

	def show(self) -> None:
		self.panel.show()

	def changeConfiguration(self, configuration: Configuration):
		self.configuration = configuration
		self.persistance.save_configuration_option(configuration)
		self.debugger_panel.set_name(configuration.name)

	@core.async
	def LaunchDebugger(self) -> core.awaitable[None]:
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

		variables = extract_variables(self.window)
		configuration_expanded = ConfigurationExpanded(configuration, variables)
		yield from self.debugger.launch(adapter_configuration, configuration_expanded)

	# TODO this could be made better
	def is_source_file(self, view: sublime.View) -> bool:
		return bool(view.file_name())

	@core.async
	def async_on_text_hovered(self, event: ui.HoverEvent) -> core.awaitable[None]:
		if not self.is_source_file(event.view):
			return

		if not self.debugger.adapter:
			return

		hover_word_seperators = self.debugger.adapter_configuration.hover_word_seperators
		hover_word_regex_match = self.debugger.adapter_configuration.hover_word_regex_match

		if hover_word_seperators:
			word = event.view.expand_by_class(event.point, sublime.CLASS_WORD_START | sublime.CLASS_WORD_END, separators=hover_word_seperators)
		else:
			word = event.view.word(event.point)

		word_string = event.view.substr(word)
		if not word_string:
			return

		if hover_word_regex_match:
			x = re.search(hover_word_regex_match, word_string)
			if not x:
				print("hover match discarded because it failed matching the hover pattern, ", word_string)
				return
			word_string = x.group()

		try:
			response = yield from self.debugger.adapter.Evaluate(word_string, self.debugger.selected_frame, 'hover')
			variable = Variable(self.debugger.adapter, "", response.result, response.variablesReference)
			event.view.add_regions('selected_hover', [word], scope="comment", flags=sublime.DRAW_NO_OUTLINE)

			def on_close() -> None:
				event.view.erase_regions('selected_hover')

			variableState = VariableStateful(variable, None)
			component = VariableStatefulComponent(variableState)
			variableState.on_dirty = component.dirty
			variableState.expand()
			ui.Popup(component, event.view, word.a, on_close=on_close)

		except Error as e:
			pass # errors trying to evaluate a hover expression should be ignored

	def on_text_hovered(self, event: ui.HoverEvent) -> None:
		core.run(self.async_on_text_hovered(event))

	def on_gutter_hovered(self, event: ui.GutterEvent) -> None:
		if self.window.active_view() != event.view:
			return
		if not self.is_source_file(event.view):
			return
		file = event.view.file_name()
		if not file:
			return
		at = event.view.text_point(event.line, 0)
		line = event.line + 1
		breakpoint = self.breakpoints.get_breakpoint(file, line)
		if breakpoint:
			breakpoint_menus.edit_breakpoint(self.breakpoints, breakpoint)


	def dispose(self) -> None:
		self.persistance.save_breakpoints(self.breakpoints)
		self.persistance.save_to_file()

		self.dispose_selected_frame()

		for d in self.disposeables:
			d.dispose()

		self.breakpoints.dispose()
		if self.debugger:
			self.debugger.dispose()
		del DebuggerInterface.instances[self.window.id()]

	def onSelectedBreakpoint(self, breakpoint: Optional[Breakpoint]) -> None:
		if breakpoint:
			self.OnExpandBreakpoint(breakpoint)

	def show_console_panel(self) -> None:
		self.panels.show(id(self.terminal))

	def show_breakpoints_panel(self) -> None:
		pass

	def show_call_stack_panel(self) -> None:
		self.panels.show(id(self.callstack_panel))

	def on_play(self) -> None:
		self.panel.show()
		self.run_async(self.LaunchDebugger())

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

	def run_async(self, awaitable: core.awaitable[None]):
		def on_error(e: Exception) -> None:
			self.terminal.log_error(str(e))
		core.run(awaitable, on_error=on_error)

	def on_run_command(self, command: str) -> None:
		self.run_async(self.debugger.evaluate(command))

	def on_navigate_to_source(self, source: Source, line: int):
		core.run(self.navigate_to_source(source, line, True))

	@core.async
	def navigate_to_source(self, source: Source, line: int, move_cursor: bool = False):
		self.navigate_soure = source
		self.navigate_line = line

		# sublime lines are 0 based

		selected_frame_generated_view = None #type: Optional[sublime.View]

		if source.sourceReference:
			if not self.debugger.adapter:
				return

			content = yield from self.debugger.adapter.GetSource(source)

			# throw out the view if it doesn't have a buffer since it was closed
			if self.selected_frame_generated_view and not self.selected_frame_generated_view.buffer_id():
				self.selected_frame_generated_view = None

			view = self.selected_frame_generated_view or self.window.new_file()
			self.selected_frame_generated_view = None
			view.set_name(source.name)
			view.set_read_only(False)
			view.run_command('debugger_replace_contents', {
				'characters': content
			})
			view.set_read_only(True)
			view.set_scratch(True)
			selected_frame_generated_view = view
		elif source.path:
			view = yield from core.sublime_open_file_async(self.window, source.path)
		else:
			return None

		view.run_command("debugger_show_line", {
			'line' : line -1,
			'move_cursor' : move_cursor
		})

		# We seem to have already selected a differn't frame in the time we loaded the view
		if source != self.navigate_soure:
			# if we generated a view close it
			if selected_frame_generated_view:
				selected_frame_generated_view.close()
			return None

		self.selected_frame_generated_view = selected_frame_generated_view
		return view


	@core.async
	def navigate_to_frame(self, thread: Thread, frame: StackFrame) -> core.awaitable[None]:
		print("Navigating to frame")

		source = frame.source

		if not source:
			self.dispose_selected_frame()
			return

		# sublime lines are 0 based
		line = frame.line - 1

		view = yield from self.navigate_to_source(source, frame.line)
		self.dispose_selected_frame()
		if view:
			self.selected_frame_line = SelectedLine(view, line, thread.stopped_text)

	def dispose_selected_frame(self) -> None:
		if self.selected_frame_generated_view:
			self.selected_frame_generated_view.close()
			self.selected_frame_generated_view = None
		if self.selected_frame_line:
			self.selected_frame_line.dispose()
			self.selected_frame_line = None

	def OnExpandBreakpoint(self, breakpoint: Breakpoint) -> None:
		breakpoint_menus.edit_breakpoint(self.breakpoints, breakpoint)


