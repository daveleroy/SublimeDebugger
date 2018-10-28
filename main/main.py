from sublime_db.core.typecheck import Tuple, List, Optional, Callable, Union, Dict, Any, Generator, Set

import sublime
import os

from sublime_db.libs import asyncio
from sublime_db import ui
from sublime_db import core

from sublime_db.main.breakpoints import Breakpoints, Breakpoint, Filter

from sublime_db.main import config
from sublime_db.main.configurations import Configuration, select_configuration, all_configurations, get_configuration_for_name, get_setting

from sublime_db.main.components.variable_component import VariablesComponent, VariableComponent, Variable
from sublime_db.main.components.breakpoint_inline_component import BreakpointInlineComponent
from sublime_db.main.components.call_stack_component import CallStackComponent
from sublime_db.main.components.console_component import EventLogComponent
from sublime_db.main.components.breakpoints_component import DebuggerComponent, STOPPED, PAUSED, RUNNING, LOADING, DebuggerComponentListener

from sublime_db.main.debug_adapter_client.client import DebugAdapterClient, StoppedEvent, OutputEvent
from sublime_db.main.debug_adapter_client.transport import start_tcp_transport, Process, TCPTransport, StdioTransport
from sublime_db.main.debug_adapter_client.types import StackFrame, EvaluateResponse

	
class Main (DebuggerComponentListener):
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
	def debuggerForWindow(window: sublime.Window) -> Optional[DebugAdapterClient]:
		main = Main.forWindow(window)
		if main:
			return main.debugAdapterClient
		return None

	@core.require_main_thread
	def __init__(self, window: sublime.Window) -> None:
		print('new Main for window', window.id())
		self.window = window
		self.disposeables = [] #type: List[Any]
		self.breakpoints = Breakpoints()
		self.view = None #type: Optional[sublime.View]
		self.eventLog = EventLogComponent()
		self.variablesComponent = VariablesComponent()
		self.callstackComponent = CallStackComponent()
		self.debuggerComponent = DebuggerComponent(self.breakpoints, self)

		self.debugAdapterClient = None #type: Optional[DebugAdapterClient]
		
		self.selectedFrameComponent = None #type: Optional[ui.Phantom]
		self.breakpointInformation = None #type: Optional[ui.Phantom]
		self.pausedWithError = False
		self.process = None #type: Optional[Process]
		self.disconnecting = False

		self.project_name = window.project_file_name() or "user"
		data = config.persisted_for_project(self.project_name)
		config_name = data.get('config_name')
		config_maybe_at_index = data.get('config_maybe_at_index')

		for bp in data.get('breakpoints', []):
			self.breakpoints.add(Breakpoint.from_json(bp))

		if config_name:
			self.configuration = get_configuration_for_name(window, config_name, config_maybe_at_index)
		else:
			self.configuration = None
			
		if self.configuration:
			self.debuggerComponent.set_name(self.configuration.name)
		else:
			self.debuggerComponent.set_name('select config')

		self.stopped_reason = ''
		self.path = window.project_file_name()
		if self.path:
			self.path = os.path.dirname(self.path)
			self.eventLog.Add('Opened In Workspace: {}'.format(self.path))
		else:
			self.eventLog.AddStderr('warning: debugger opened in a window that is not part of a project')
			
		print('Creating a window: h')
		
		self.disposeables.extend([
			ui.view_gutter_hovered.add(self.on_gutter_hovered),
			ui.view_text_hovered.add(self.on_text_hovered),
			ui.view_drag_select.add(self.on_drag_select),
		])
		
		mode = get_setting(window.active_view(), 'display')

		if mode == 'window':
			sublime.run_command("new_window")
			new_window = sublime.active_window()
			output = new_window.new_file()
			new_window.set_minimap_visible(False)
			new_window.set_sidebar_visible(False)
			new_window.set_tabs_visible(False)
			new_window.set_menu_visible(False)
			new_window.set_status_bar_visible(False)
		elif mode == 'view':
			output = self.window.new_file()
		elif mode == 'output':
			output = self.window.create_output_panel('debugger')
			self.window.run_command('show_panel', {
				'panel': 'output.debugger'
			})
		else:
			core.display('expected setting "mode" to be one of "window", "view" or "output", found "{}"'.format(mode))
			return
		
		output.run_command('insert', {
			'characters': "      "
		})
		output.set_scratch(True)
		output.set_read_only(True)
		output.set_name('Debugger')
		view_settings = output.settings()
		view_settings.set("is_widget", True)
		view_settings.set("gutter", False)
		view_settings.set("margin", 0)
		view_settings.set("always_show_minimap_viewport", False)		
		self.view = output

		self.disposeables.extend([
			ui.Phantom(self.debuggerComponent, output, sublime.Region(1, 1), sublime.LAYOUT_INLINE),
			ui.Phantom(self.callstackComponent, output, sublime.Region(1, 2), sublime.LAYOUT_INLINE),
			ui.Phantom(self.variablesComponent, output, sublime.Region(1, 3), sublime.LAYOUT_INLINE),
			ui.Phantom(self.eventLog, output, sublime.Region(1, 4), sublime.LAYOUT_INLINE)
		])

		self.breakpoints.onRemovedBreakpoint.add(lambda b: self.clearBreakpointInformation())
		self.breakpoints.onChangedBreakpoint.add(self.onChangedBreakpoint)
		self.breakpoints.onChangedFilter.add(self.onChangedFilter)
		self.breakpoints.onSelectedBreakpoint.add(self.onSelectedBreakpoint)
		
	def show(self) -> None:
		self.window.run_command('show_panel', {
			'panel': 'output.debugger'
		})
	
	@core.async
	def EditSettings (self) -> Generator[Any, None, None]:
		index = 0
		if self.configuration:
			index = self.configuration.index

		configuration = yield from select_configuration(self.window, index)
		print('Selected configuration:', configuration)
		if configuration:
			persist = config.persisted_for_project(self.project_name)
			persist['config_name'] = configuration.name
			persist['config_maybe_at_index'] = configuration.index
			config.save_data()
			self.configuration = configuration
			self.debuggerComponent.set_name(configuration.name)
	@core.async
	def LaunchDebugger (self) -> Generator[Any, None, None]:
		self.KillDebugger()
		self.eventLog.clear()
		self.eventLog.Add('Starting debugger...')
		self.debuggerComponent.setState(LOADING)
		try:
			if not self.configuration:
				yield from self.EditSettings()

			if not self.configuration:
				return

			config = self.configuration

			debuggers = get_setting(self.window.active_view(), 'adapters', {})
			
			debugger = debuggers.get(config.type)
			assert debugger, 'no debugger named {}'.format(config.type)

			adapter_type_config = sublime.expand_variables(debugger, self.window.extract_variables())
			command = adapter_type_config.get('command')
			assert command, 'expected "command" in debugger settings'

			port = adapter_type_config.get('tcp_port')

			#If there is a command to run for this debugger run it now
			if port:
				print('Starting Process: {}'.format(command))
				try:
					self.process = Process(command, 
						on_stdout = lambda msg: self.eventLog.Add(msg), 
						on_stderr = lambda msg: self.eventLog.Add(msg))
				except Exception as e:
					self.eventLog.AddStderr('Failed to start debug adapter process: {}'.format(e))
					self.eventLog.AddStderr('Command in question: {}'.format(command))
					core.display('Failed to start debug adapter process: Check the Event Log for more details')

				address = adapter_type_config.get('tcp_address', 'localhost')
				try:
					transport = yield from start_tcp_transport(address, port)
				except Exception as e:
					self.eventLog.AddStderr('Failed to connect to debug adapter: {}'.format(e))
					self.eventLog.AddStderr('address: {} port: {}'.format(address, port))
					core.display('Failed to connect to debug adapter: Check the Event Log for more details and messages from the debug adapter process?')
					return
			else:
				# dont monitor stdout the StdioTransport users it
				self.process = Process(command, 
						on_stdout = None, 
						on_stderr = lambda msg: self.eventLog.Add(msg))
				
				transport = StdioTransport(self.process)

		except Exception as e:
			core.display(e)
			return
		
		debugAdapterClient = DebugAdapterClient(transport)
		self.debugAdapterClient = debugAdapterClient

		def onOutput(event: OutputEvent) -> None:
			category = event.category
			msg = event.text
			variablesReference = event.variablesReference

			if variablesReference and self.debugAdapterClient:
				variable = Variable(self.debugAdapterClient, msg, '', variablesReference)
				self.eventLog.AddVariable(variable)
			elif category == "stdout":
				self.eventLog.AddStdout(msg)
			elif category == "stderr":
				self.eventLog.AddStderr(msg)
			elif category == "console":
				self.eventLog.Add(msg)

		def onStopped(event: StoppedEvent) -> None:
			self.pausedWithError = debugAdapterClient.stoppedOnError
			self.debuggerComponent.setState(PAUSED)
			self.eventLog.Add(event.reason)
			self.stopped_reason = event.reason
			if event.text:
				self.eventLog.Add(event.text)
		def onContinued(event: Any) -> None:
			self.debuggerComponent.setState(RUNNING)
		def onExited(event: Any) -> None:
			self.KillDebugger()
		def onThreads(event: Any) -> None:
			self.callstackComponent.setThreads(debugAdapterClient, debugAdapterClient.threads, self.pausedWithError)
		def onVariables(event: Any) -> None:
			self.variablesComponent.set_variables(debugAdapterClient.variables)
		def onSelectedStackFrame(frame: Optional[StackFrame]) -> None:
			self.onSelectedStackFrame(frame)
			self.callstackComponent.dirty_threads()
		def on_error(error: str) -> None:
			self.eventLog.AddStderr(error)

		debugAdapterClient.onSelectedStackFrame.add(onSelectedStackFrame)
		debugAdapterClient.onExited.add(onExited)
		debugAdapterClient.onOutput.add(onOutput)
		debugAdapterClient.onStopped.add(onStopped)
		debugAdapterClient.onContinued.add(onContinued)
		debugAdapterClient.onThreads.add(onThreads)
		debugAdapterClient.onVariables.add(onVariables)
		debugAdapterClient.on_error_event.add(on_error)

		# this is a bit of a weird case. Initialized will happen at some point in time
		# it depends on when the debug adapter chooses it is ready for configuration information
		# when it does happen we can then add all the breakpoints and complete the configuration
		@core.async
		def Initialized() -> Generator[Any, None, None]:
			yield from debugAdapterClient.Initialized()
			yield from debugAdapterClient.AddBreakpoints(self.breakpoints)
			yield from debugAdapterClient.ConfigurationDone()
		core.run(Initialized())
		adapter_config = sublime.expand_variables(config.all, self.window.extract_variables())

		print ('Adapter initialize')
		body = yield from debugAdapterClient.Initialize()
		for filter in body.get('exceptionBreakpointFilters', []):
			id = filter['filter']
			name = filter['label']
			default = filter.get('default', False)
			self.breakpoints.add_filter(id, name, default)
		print ('Adapter initialized: success!')
		if config.request == 'launch':
			yield from debugAdapterClient.Launch(adapter_config)
		elif config.request == 'attach':
			yield from debugAdapterClient.Attach(adapter_config)
		else:
			raise Exception('expected configuration to have request of either "launch" or "attach" found {}'.format(config.request))
		
		print ('Adapter has been launched/attached')
		# At this point we are running?
		self.debuggerComponent.setState(RUNNING)


	def dispose_adapter(self) -> None:
		if self.selectedFrameComponent: 
			self.selectedFrameComponent.dispose()
			self.selectedFrameComponent = None

		
		self.variablesComponent.clear()
		self.callstackComponent.clear()

		if self.debugAdapterClient:
			self.debugAdapterClient.dispose()
			self.debugAdapterClient = None

		if self.process:
			self.process.dispose()
			self.process = None

		self.debuggerComponent.setState(STOPPED)
		self.breakpoints.clear_breakpoint_results()

	@core.async
	def Disconnect(self) -> core.awaitable[None]:
		print('Disconnect Adapter')
		self.debuggerComponent.setState(LOADING)
		assert self.debugAdapterClient
		self.disconnecting = True
		yield from self.debugAdapterClient.Disconnect()
		self.dispose_adapter()
		self.disconnecting = False
		
	def KillDebugger(self) -> None:
		print('Kill Adapter')
		self.dispose_adapter()
		self.disconnecting = False

	def clearBreakpointInformation(self) -> None:
		if self.breakpointInformation:
			self.breakpointInformation.dispose()
			self.breakpointInformation = None

	def on_drag_select(self, view: sublime.View) -> None:
		self.clearBreakpointInformation()

	def on_text_hovered(self, event: ui.HoverEvent) -> None:
		if self.debugAdapterClient:
			word = event.view.word(event.point)
			expr = event.view.substr(word)

			def complete(response: Optional[EvaluateResponse]) -> None:
				if not response:
					return
				if self.debugAdapterClient:
					variable = Variable(self.debugAdapterClient, response.result, '', response.variablesReference)
					event.view.add_regions('selected_hover', [word], scope = "comment", flags = sublime.DRAW_NO_OUTLINE)
					def on_close() -> None:
						event.view.erase_regions('selected_hover')
					ui.Popup(VariableComponent(variable), event.view, word.a, on_close = on_close)
					
			core.run(self.debugAdapterClient.Evaluate(expr, 'hover'), complete)

	def on_gutter_hovered(self, event: ui.GutterEvent) -> None:
		file = event.view.file_name() 
		if not file:  return #ignore if the view does not have a file

		at = event.view.text_point(event.line, 0)

		breakpoint =  self.breakpoints.get_breakpoint(file, event.line + 1)
		if not breakpoint:
			return
		self.breakpoints.select_breakpoint(breakpoint)

	def dispose(self) -> None:
		json_breakpoints = []
		for bp in self.breakpoints.breakpoints:
			json_breakpoints.append(bp.into_json())

		persist = config.persisted_for_project(self.project_name)
		persist['breakpoints'] = json_breakpoints
		config.save_data()

		if self.selectedFrameComponent:
			self.selectedFrameComponent.dispose()
			self.selectedFrameComponent = None

		self.clearBreakpointInformation()

		for d in self.disposeables:
			d.dispose()

		self.KillDebugger()
		self.breakpoints.dispose()
		self.window.destroy_output_panel('debugger')
		del Main.instances[self.window.id()]
	
	def onChangedFilter(self, filter: Filter) -> None:
		if self.debugAdapterClient:
			core.run(self.debugAdapterClient.setExceptionBreakpoints(self. breakpoints.filters))
	def onChangedBreakpoint(self, breakpoint: Breakpoint) -> None:
		if self.debugAdapterClient:
			file = breakpoint.file
			breakpoints = self.breakpoints.breakpoints_for_file(file)
			core.run(self.debugAdapterClient.SetBreakpointsFile(file, breakpoints))

	def onSelectedBreakpoint(self, breakpoint: Optional[Breakpoint]) -> None:
		if breakpoint:
			self.OnExpandBreakpoint(breakpoint)
		else:
			self.clearBreakpointInformation()

	def OnSettings(self) -> None:
		core.run(self.EditSettings())
	def OnPlay(self) -> None:
		core.run(self.LaunchDebugger())
	def OnStop(self) -> None:
		if self.disconnecting:
			self.KillDebugger()
		else:
			core.run(self.Disconnect())
	def OnResume(self) -> None:
		assert self.debugAdapterClient
		core.run(self.debugAdapterClient.Resume())
	def OnPause(self) -> None:
		assert self.debugAdapterClient
		core.run(self.debugAdapterClient.Pause())
	def OnStepOver(self) -> None:
		assert self.debugAdapterClient
		core.run(self.debugAdapterClient.StepOver())
	def OnStepIn(self) -> None:
		assert self.debugAdapterClient
		core.run(self.debugAdapterClient.StepIn())
	def OnStepOut(self) -> None:
		assert self.debugAdapterClient
		core.run(self.debugAdapterClient.StepOut())

	def add_selected_stack_frame_component(self, view: sublime.View, line: int) -> None:
		if self.selectedFrameComponent:
			self.selectedFrameComponent.dispose()
			self.selectedFrameComponent = None

		if not self.debugAdapterClient:
			return
		if not self.debugAdapterClient.selected_frame:
			return

		pt = view.text_point(line + 1, 0)

		max = view.viewport_extent()[0]/view.em_width() - 3

		pt_current_line = view.text_point(line, 0)
		line_current = view.line(pt_current_line)
		region =  sublime.Region(pt-1, pt-1)

		layout = sublime.LAYOUT_INLINE
		if line_current.b - line_current.a > max:
			pt = view.text_point(line - 1, 0)
			region =  sublime.Region(pt, pt)
			layout = sublime.LAYOUT_BELOW

		variables = ui.Segment(items = [
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
			ui.Label(self.stopped_reason, padding_left = 1,  padding_right = 1, color = 'secondary')
		])
		self.selectedFrameComponent = ui.Phantom(variables, view, region, layout)

	def onSelectedStackFrame(self, frame: Optional[StackFrame]) -> None:
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
			
	def OnExpandBreakpoint(self, breakpoint: Breakpoint) -> None:	
		@core.async
		def a() -> core.awaitable[None]:
			view = yield from core.sublime_open_file_async(sublime.active_window(), breakpoint.file, breakpoint.line)
			at = view.text_point(breakpoint.line - 1, 0)
			view.sel().clear()
			self.clearBreakpointInformation()
			self.breakpointInformation = ui.Phantom(BreakpointInlineComponent(breakpoints = self.breakpoints, breakpoint = breakpoint), view, sublime.Region(at, at), sublime.LAYOUT_BELOW)
		core.run(a())


@core.async
def startup_main_thread() -> None:
	print('Starting up')
	ui.startup()
	ui.import_css('{}/{}'.format(sublime.packages_path(), 'sublime_db/main/components/components.css'))
	
	was_opened_at_startup = set() #type: Set[int]
	
	def on_view_activated (view: sublime.View) -> None:
		window = view.window()
		if window and not window.id() in was_opened_at_startup and get_setting(view, 'open_at_startup', False):
			was_opened_at_startup.add(window.id())
			Main.forWindow(window, True)

	ui.view_activated.add(on_view_activated)

def startup() -> None:
	core.startup()
	core.run(startup_main_thread())

import threading

@core.async
def shutdown_main_thread(event: threading.Event) -> None:
	# we just want to ensure that we still set the event if we had an exception somewhere
	# otherwise shutdown could lock us up
	try:
		print('shutdown')
		for key, instance in dict(Main.instances).items():
			instance.dispose()
		Main.instances = {}
		ui.shutdown()
	except Exception as e:
		raise e
	finally:
		event.set()

def shutdown() -> None:
	event = threading.Event()
	core.run(shutdown_main_thread(event))
	event.wait()
	core.shutdown()
