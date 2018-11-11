from sublime_db.core.typecheck import Tuple, List, Optional, Callable, Union, Dict, Any, Set

import sublime
import sublime_plugin
import os

from sublime_db import ui
from sublime_db import core

from .breakpoints import Breakpoints, Breakpoint, Filter

from .util import get_setting, register_on_changed_setting
from .configurations import Configuration, AdapterConfiguration, select_or_add_configuration
from .config import PersistedData

from .components.variable_component import VariableComponent, Variable
from .components.breakpoint_inline_component import BreakpointInlineComponent
from .components.debugger_panel import DebuggerPanel, DebuggerPanelCallbacks, STOPPED, PAUSED, RUNNING, LOADING
from .components.callstack_panel import CallStackPanel
from .components.console_panel import ConsolePanel
from .components.variables_panel import VariablesPanel
from .repl import run_repl_command

from .debugger import (
	DebuggerState,
	OutputEvent,
	StackFrame,
	Scope,
	Thread,
	EvaluateResponse,
	DebugAdapterClient
)

from .output_panel import OutputPhantomsPanel, PanelInputHandler

class Main (DebuggerPanelCallbacks):
	instances = {} #type: Dict[int, Main]
	@staticmethod
	def forWindow(window: sublime.Window, create: bool = False) -> 'Optional[Main]':
		instance = Main.instances.get(window.id())
		if not instance and create:
			main = Main(window)
			Main.instances[window.id()] = main
			return main
		return instance
	@staticmethod
	def debuggerForWindow(window: sublime.Window) -> Optional[DebuggerState]:
		main = Main.forWindow(window)
		if main:
			return main.debugger
		return None
	
	def create_input_handler(self, window: sublime.Window, label: str, hint: str, on_change: Callable[[str], None],  on_done: Callable[[Optional[str]], None]) -> ui.InputHandler:
		return PanelInputHandler(self.panel, label, hint, on_change, on_done)

	def get_run_command(self) -> None:
		def on_done(value: Optional[str]) -> None:
			if value:
				core.run(run_repl_command(value, self.debugger, self.console_panel))
		def on_change(value: str) -> None:
			pass
		PanelInputHandler(self.panel, label = 'Command', hint = "", on_change = on_change, on_done = on_done)


	@core.require_main_thread
	def __init__(self, window: sublime.Window) -> None:
		print('new Main for window', window.id())
		ui.set_create_input_handler(window, self.create_input_handler)


		self.input_open = False
		self.input_handler = None #type: Optional[PanelInputHandler]
		self.window = window
		self.disposeables = [] #type: List[Any]
		self.breakpoints = Breakpoints()

		self.console_panel = ConsolePanel(self.get_run_command)
		self.variables_panel = VariablesPanel()
		self.callstack_panel = CallStackPanel()
		self.debugger_panel = DebuggerPanel(self.breakpoints, self)
		
		self.selectedFrameComponent = None #type: Optional[ui.Phantom]
		self.breakpointInformation = None #type: Optional[ui.Phantom]

		def on_state_changed (state: int) -> None:
			if state == DebuggerState.stopped:
				self.breakpoints.clear_breakpoint_results()
				self.debugger_panel.setState(STOPPED)
			elif state == DebuggerState.running:
				self.debugger_panel.setState(RUNNING)
			elif state == DebuggerState.paused:
				self.debugger_panel.setState(PAUSED)
			elif state == DebuggerState.stopping or state == DebuggerState.starting:
				self.debugger_panel.setState(LOADING)

		def on_threads (threads: List[Thread]) -> None:
			self.callstack_panel.setThreads(self.debugger.adapter, threads, False)

		def on_scopes (scopes: List[Scope]) -> None:
			self.variables_panel.set_scopes(scopes)

		def on_selected_frame(frame: Optional[StackFrame]) -> None:
			if not frame:
				if self.selectedFrameComponent: 
					self.selectedFrameComponent.dispose()
					self.selectedFrameComponent = None
				return
			if not frame.internal:
				line = frame.line - 1
				def complete(view: sublime.View) -> None:
					self.add_selected_stack_frame_component(view, line)
			
			core.run(core.sublime_open_file_async(self.window, frame.file, line), complete)

		def on_output (event: OutputEvent) -> None:
			category = event.category
			msg = event.text
			variablesReference = event.variablesReference

			if variablesReference and self.debugger.adapter:
				variable = Variable(self.debugger.adapter, msg, '', variablesReference)
				self.console_panel.AddVariable(variable)
			elif category == "stdout":
				self.console_panel.AddStdout(msg)
			elif category == "stderr":
				self.console_panel.AddStderr(msg)
			elif category == "console":
				self.console_panel.Add(msg)

		self.debugger = DebuggerState(
			on_state_changed = on_state_changed, 
			on_threads = on_threads,
			on_scopes = on_scopes,
			on_output = on_output,
			on_selected_frame = on_selected_frame)

		self.panel = OutputPhantomsPanel(window, 'Debugger')
		self.panel.show()
		
		output = self.panel.view
		self.view = output #type: sublime.View
	
		self.project_name = window.project_file_name() or "user"
		self.persistance = PersistedData(self.project_name)

		for breakpoint in self.persistance.load_breakpoints():
			self.breakpoints.add(breakpoint)

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
			ui.view_drag_select.add(self.on_drag_select),
		])

		offset = self.panel.phantom_location()
		
		self.disposeables.extend([
			ui.Phantom(self.debugger_panel, output, offset, sublime.LAYOUT_INLINE),
			ui.Phantom(self.callstack_panel, output, offset, sublime.LAYOUT_INLINE),
			ui.Phantom(self.variables_panel, output, offset, sublime.LAYOUT_INLINE),
			ui.Phantom(self.console_panel, output, offset, sublime.LAYOUT_INLINE)
		])

		self.breakpoints.onRemovedBreakpoint.add(lambda b: self.clearBreakpointInformation())
		self.breakpoints.onChangedBreakpoint.add(self.onChangedBreakpoint)
		self.breakpoints.onChangedFilter.add(self.onChangedFilter)
		self.breakpoints.onSelectedBreakpoint.add(self.onSelectedBreakpoint)
		
		active_view = self.window.active_view()

		if active_view:
			self.disposeables.append(
				register_on_changed_setting(active_view, self.on_settings_updated)
			)
		else:
			print('Failed to find active view to listen for settings changes')

	def load_configurations (self) -> None:
		data = self.window.project_data()
		if data:
			data.setdefault('settings', {}).setdefault('debug.configurations', [])
			self.window.set_project_data(data)

		adapters = {}
		
		for adapter_name, adapter_json in get_setting(self.window.active_view(), 'adapters', {}).items():
			try:
				adapter = AdapterConfiguration.from_json(adapter_name, adapter_json, self.window)
				adapters[adapter.type] = adapter
			except Exception as e:
				core.display('There was an error creating a AdapterConfiguration {}'.format(e))

		configurations = [] 
		for index, configuration_json in enumerate(get_setting(self.window.active_view(), 'configurations', [])):
			configuration = Configuration.from_json(configuration_json)
			configuration.all = sublime.expand_variables(configuration.all, self.window.extract_variables()) 
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
	
	@core.async
	def SelectConfiguration (self) -> core.awaitable[None]:
		selected_index = None #type: Optional[int]
		if self.configuration:
			selected_index = self.configuration.index

		configuration = yield from select_or_add_configuration(self.window, selected_index, self.configurations, self.adapters)
		print('Selected configuration:', configuration)
		if configuration:
			self.persistance.save_configuration_option(configuration)
			self.configuration = configuration
			self.debugger_panel.set_name(configuration.name)

	@core.async
	def LaunchDebugger (self) -> core.awaitable[None]:
		self.console_panel.clear()
		self.console_panel.Add('Starting debugger...')
		try:
			if not self.configuration:
				yield from self.SelectConfiguration()

			if not self.configuration:
				return

			configuration = self.configuration

			adapter_configuration = self.adapters.get(configuration.type)
			if not adapter_configuration:
				raise Exception('Unable to find debug adapter with the type name "{}"'.format(configuration.type))

		except Exception as e:
			core.log_exception()
			core.display(e)
			return
		
		yield from self.debugger.launch(adapter_configuration, configuration, self.breakpoints)

	def clearBreakpointInformation(self) -> None:
		if self.breakpointInformation:
			self.breakpointInformation.dispose()
			self.breakpointInformation = None

	def on_drag_select(self, view: sublime.View) -> None:
		if view != self.view:
			self.clearBreakpointInformation()
			self.panel.close_input()

	# TODO this could be made better
	def is_source_file(self, view: sublime.View)-> bool:
		return bool(view.file_name())

	def on_text_hovered(self, event: ui.HoverEvent) -> None:
		if not self.is_source_file(event.view): return

		if self.debugger.adapter:
			word = event.view.word(event.point)
			expr = event.view.substr(word)

			def complete(response: Optional[EvaluateResponse]) -> None:
				if not response:
					return
				if self.debugger.adapter:
					variable = Variable(self.debugger.adapter, response.result, '', response.variablesReference)
					event.view.add_regions('selected_hover', [word], scope = "comment", flags = sublime.DRAW_NO_OUTLINE)
					def on_close() -> None:
						event.view.erase_regions('selected_hover')
					ui.Popup(VariableComponent(variable), event.view, word.a, on_close = on_close)
					
			core.run(self.debugger.adapter.Evaluate(expr, 'hover'), complete)

	def on_gutter_hovered(self, event: ui.GutterEvent) -> None:
		if not self.is_source_file(event.view): return
		file = event.view.file_name()
		if not file:
			return

		at = event.view.text_point(event.line, 0)

		breakpoint =  self.breakpoints.get_breakpoint(file, event.line + 1)
		if not breakpoint:
			return
		self.breakpoints.select_breakpoint(breakpoint)

	def dispose(self) -> None:
		self.persistance.save_breakpoints(self.breakpoints)
		self.persistance.save_to_file()

		if self.selectedFrameComponent:
			self.selectedFrameComponent.dispose()
			self.selectedFrameComponent = None

		self.clearBreakpointInformation()

		for d in self.disposeables:
			d.dispose()

		self.breakpoints.dispose()
		self.window.destroy_output_panel('debugger')
		del Main.instances[self.window.id()]
	
	def onChangedFilter(self, filter: Filter) -> None:
		self.debugger.update_exception_filters(self.breakpoints.filters)

	def onChangedBreakpoint(self, breakpoint: Breakpoint) -> None:
		file = breakpoint.file
		breakpoints = self.breakpoints.breakpoints_for_file(file)
		self.debugger.update_breakpoints_for_file(file, breakpoints)

	def onSelectedBreakpoint(self, breakpoint: Optional[Breakpoint]) -> None:
		if breakpoint:
			self.OnExpandBreakpoint(breakpoint)
		else:
			self.clearBreakpointInformation()

	def OnSettings(self) -> None:
		core.run(self.SelectConfiguration())
	def OnPlay(self) -> None:
		core.run(self.LaunchDebugger())
	def OnStop(self) -> None:
		core.run(self.debugger.stop())
	def OnResume(self) -> None:
		core.run(self.debugger.resume())
	def OnPause(self) -> None:
		core.run(self.debugger.pause())
	def OnStepOver(self) -> None:
		core.run(self.debugger.step_over())
	def OnStepIn(self) -> None:
		core.run(self.debugger.step_in())
	def OnStepOut(self) -> None:
		core.run(self.debugger.step_out())
	def add_selected_stack_frame_component(self, view: sublime.View, line: int) -> None:
		if self.selectedFrameComponent:
			self.selectedFrameComponent.dispose()
			self.selectedFrameComponent = None

		if not self.debugger:
			return
		if not self.debugger.selected_frame:
			return

		pt = view.text_point(line + 1, 0)

		max = view.viewport_extent()[0]/view.em_width() - 3

		pt_current_line = view.text_point(line, 0)
		line_current = view.line(pt_current_line)
		at =  pt-1

		layout = sublime.LAYOUT_INLINE
		if line_current.b - line_current.a > max:
			at = view.text_point(line - 1, 0)
			layout = sublime.LAYOUT_BELOW

		variables = ui.Box(items = [
			ui.Label('', padding_left = 1),
			ui.Button(self.OnResume, items = [
				ui.Img(ui.Images.shared.play)
			]),
			ui.Button(self.OnStepOver, items = [
				ui.Img(ui.Images.shared.down)
			]),
			ui.Button(self.OnStepOut, items = [
				ui.Img(ui.Images.shared.left)
			]),
			ui.Button(self.OnStepIn, items = [
				ui.Img(ui.Images.shared.right)
			]),
			ui.Label(self.debugger.stopped_reason, padding_left = 1,  padding_right = 1.5, color = 'secondary')
		])
		self.selectedFrameComponent = ui.Phantom(variables, view, at, layout)
			
	def OnExpandBreakpoint(self, breakpoint: Breakpoint) -> None:	
		@core.async
		def a() -> core.awaitable[None]:
			view = yield from core.sublime_open_file_async(sublime.active_window(), breakpoint.file, breakpoint.line)
			at = view.text_point(breakpoint.line - 1, 0)
			view.sel().clear()
			self.clearBreakpointInformation()
			self.breakpointInformation = ui.Phantom(BreakpointInlineComponent(breakpoints = self.breakpoints, breakpoint = breakpoint), view, at, sublime.LAYOUT_BELOW)
		core.run(a())

