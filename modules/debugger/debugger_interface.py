from sublime_db.modules.core.typecheck import Tuple, List, Optional, Callable, Union, Dict, Any, Set

import sublime
import sublime_plugin
import os
import subprocess
import re
import json

from sublime_db.modules import ui
from sublime_db.modules import core

from .breakpoints import Breakpoints, Breakpoint, Filter

from .util import get_setting, register_on_changed_setting, extract_variables
from .configurations import Configuration, AdapterConfiguration
from .config import PersistedData

from .components.variable_component import VariableStateful, VariableStatefulComponent, Variable
from .components.debugger_panel import DebuggerPanel, DebuggerPanelCallbacks, STOPPED, PAUSED, RUNNING, LOADING
from .components.breakpoints_panel import BreakpointsPanel, show_breakpoint_options
from .components.callstack_panel import CallStackPanel
from .components.console_panel import ConsolePanel
from .components.variables_panel import VariablesPanel
from .components.pages_panel import TabbedPanel
from .components.selected_line import SelectedLine

from .debugger import (
	DebuggerState,
	OutputEvent,
	StackFrame,
	Scope,
	Thread,
	EvaluateResponse,
	DebugAdapterClient,
	Error,
	Source
)

from .output_panel import OutputPhantomsPanel
from .commands.commands import Autocomplete, run_command_from_pallete, AutoCompleteTextInputHandler
from .commands import breakpoint_menus
from .commands import select_configuration


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
			main = DebuggerInterface(window)
			DebuggerInterface.instances[window.id()] = main
			return main
		return instance

	@staticmethod
	def debuggerForWindow(window: sublime.Window) -> Optional[DebuggerState]:
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
			self.debugger.evaluate(expression)
			self.open_repl_console()
		ui.run_input_command(input, run)		

	@core.require_main_thread
	def __init__(self, window: sublime.Window) -> None:

		data = window.project_data()
		project_name = window.project_file_name()
		if not data or not project_name:
			sublime.error_message("Debugger must be run inside a sublime project")
			return

		# ensure we have debug configurations added to the project file
		data.setdefault('settings', {}).setdefault('debug.configurations', [])
		window.set_project_data(data)

		autocomplete = Autocomplete.create_for_window(window)

		self.input_open = False
		self.window = window
		self.disposeables = [] #type: List[Any]
		self.breakpoints = Breakpoints()

		self.console_panel = ConsolePanel(self.open_repl_console, self.on_navigate_to_source)
		self.variables_panel = VariablesPanel()
		self.callstack_panel = CallStackPanel()
		self.breakpoints_panel = BreakpointsPanel(self.breakpoints, self.onSelectedBreakpoint)

		def on_breakpoint_more():
			show_breakpoint_options(self.breakpoints)

		self.pages_panel = TabbedPanel([
			("Breakpoints", self.breakpoints_panel, on_breakpoint_more),
			("Call Stack", self.callstack_panel, None),
			("Console", self.console_panel, self.console_panel.open_console_menu),
		], 0)
		self.debugger_panel = DebuggerPanel(self)

		self.selected_frame_line = None #type: Optional[SelectedLine]
		self.selected_frame_generated_view = None #type: Optional[sublime.View]

		def on_state_changed(state: int) -> None:
			if state == DebuggerState.stopped:
				self.breakpoints.clear_breakpoint_results()
				self.debugger_panel.setState(STOPPED)
				self.show_console_panel()
			elif state == DebuggerState.running:
				self.debugger_panel.setState(RUNNING)
			elif state == DebuggerState.paused:
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
			elif state == DebuggerState.stopping or state == DebuggerState.starting:
				self.debugger_panel.setState(LOADING)

		def on_scopes(scopes: List[Scope]) -> None:
			self.variables_panel.set_scopes(scopes)

		def on_selected_frame(thread: Optional[Thread], frame: Optional[StackFrame]) -> None:
			if frame and thread:
				self.run_async(self.navigate_to_frame(thread, frame))
			else:
				self.dispose_selected_frame()

		def on_output(event: OutputEvent) -> None:
			variablesReference = event.variablesReference

			if variablesReference and self.debugger.adapter:
				# this seems to be what vscode does it ignores the actual message here.
				# Some of the messages are junk like "output" that we probably don't want to display
				@core.async
				def appendVariabble() -> core.awaitable[None]:
					variables = yield from self.debugger.adapter.GetVariables(variablesReference)
					for variable in variables:
						variable.name = "" # this is what vs code does?
						self.console_panel.add_variable(variable, event.source, event.line)
					self.pages_panel.modified(2)

				# this could make variable messages appear out of order. Do we care??
				self.run_async(appendVariabble())
			else:
				self.console_panel.add(event)

		def on_threads_stateful(threads: Any):
			self.callstack_panel.update(self.debugger, threads)

		self.debugger = DebuggerState(
			self.breakpoints,
			on_state_changed=on_state_changed,
			on_scopes=on_scopes,
			on_output=on_output,
			on_selected_frame=on_selected_frame,
			on_threads_stateful=on_threads_stateful)

		self.panel = OutputPhantomsPanel(window, 'Debugger')
		self.panel.show()
		self.view = self.panel.view #type: sublime.View

		self.persistance = PersistedData(project_name)
		self.persistance.load_breakpoints(self.breakpoints)

		self.load_configurations()

		self.stopped_reason = ''
		self.path = window.project_file_name()
		if self.path:
			self.path = os.path.dirname(self.path)
			self.console_panel.Add('Opened In Workspace: {}'.format(self.path))
		else:
			self.console_panel.AddStderr('warning: debugger opened in a window that is not part of a project')

		print('Creating a window: h')

		self.disposeables.extend([
			self.panel,
			ui.view_gutter_hovered.add(self.on_gutter_hovered),
			ui.view_text_hovered.add(self.on_text_hovered),
			self.breakpoints.onSelectedBreakpoint.add(self.onSelectedBreakpoint)
		])


		phantom_location = self.panel.phantom_location()
		self.disposeables.extend([
			ui.Phantom(self.debugger_panel, self.view, sublime.Region(phantom_location, phantom_location + 0), sublime.LAYOUT_INLINE),
			ui.Phantom(self.pages_panel, self.view, sublime.Region(phantom_location, phantom_location + 1), sublime.LAYOUT_INLINE),
			ui.Phantom(self.variables_panel, self.view, sublime.Region(phantom_location, phantom_location + 2), sublime.LAYOUT_INLINE),
		])


		active_view = self.window.active_view()

		if active_view:
			self.disposeables.append(
				register_on_changed_setting(active_view, self.on_settings_updated)
			)
		else:
			print('Failed to find active view to listen for settings changes')


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
			configurations_json = sublime.expand_variables(configurations_json, variables)

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
		self.console_panel.clear()
		self.console_panel.Add('Console cleared...')
		try:
			if not self.configuration:
				self.console_panel.AddStderr("Add or select a configuration to begin debugging")
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

		yield from self.debugger.launch(adapter_configuration, configuration)

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
			response = yield from self.debugger.adapter.Evaluate(word_string, self.debugger.frame, 'hover')
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
		self.pages_panel.selected(2)

	def show_breakpoints_panel(self) -> None:
		self.pages_panel.selected(0)

	def show_call_stack_panel(self) -> None:
		self.pages_panel.selected(1)

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
			self.console_panel.AddStderr(str(e))
			self.pages_panel.modified(2)
		core.run(awaitable, on_error=on_error)


	def on_navigate_to_source(self, source: Source, line: int):
		core.run(self.navigate_to_source(source, line))

	@core.async
	def navigate_to_source(self, source: Source, line: int):
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
			view.run_command('sublime_debug_replace_contents', {
				'characters': content
			})
			view.set_read_only(True)
			view.set_scratch(True)
			selected_frame_generated_view = view
		elif source.path:
			view = yield from core.sublime_open_file_async(self.window, source.path)
		else:
			return None

		view.show(view.text_point(line - 1, 0), True)
		
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


