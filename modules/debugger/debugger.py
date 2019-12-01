from ..typecheck import *

import sublime

from .. import core, dap

from ..dap.transport import (
	Process,
	StdioTransport
)

from .terminal import Terminal, TerminalProcess, TerminalStandard

from .adapter import (
	ConfigurationExpanded,
	Adapter
)
from .breakpoints import (
	Breakpoints,
	SourceBreakpoint,
)
from .thread import (
	ThreadStateful
)

from .build import build

from .modules import Modules
from .sources import Sources
from .watch import Watch
from .variables import Variables

class DebuggerStateful(dap.ClientEventsListener):
	stopped = 0
	paused = 1
	running = 2

	starting = 3
	stopping = 4

	def __init__(
		self,
		on_state_changed: Callable[[int], None],
		on_output: Callable[[dap.OutputEvent], None],
		on_selected_frame: Callable[[Optional[dap.Thread], Optional[dap.StackFrame]], None],
		on_threads_stateful: Callable[[List[ThreadStateful]], None],
		on_terminals: Callable[[List[Terminal]], None],
	) -> None:

		self.on_state_changed = on_state_changed
		self.on_threads_stateful = on_threads_stateful
		self.on_output = on_output
		self.on_selected_frame = on_selected_frame
		self.on_terminals = on_terminals

		self.adapter = None #type: Optional[dap.Client]
		self.process = None #type: Optional[Process]
		self.launching_async = None

		self.launch_request = True

		self.selected_frame = None #type: Optional[Union[dap.StackFrame, ThreadStateful]]
		self.selected_thread_explicitly = False
		self.selected_threadstateful = None #type: Optional[ThreadStateful]

		self.threads_stateful = [] #type: List[ThreadStateful]
		self.threads_stateful_from_id = {} #type: Dict[int, ThreadStateful]

		self.terminals = [] #type: List[Terminal]
		self._state = DebuggerStateful.stopped

		self.disposeables = [] #type: List[Any]


		def on_send_data_breakpoints(data_breakpoints):
			core.run(self.set_data_breakpoints())

		def on_send_function_breakpoints(function_breakpoints):
			core.run(self.set_function_breakpoints())
		
		def on_send_filters(filters):
			if not self.adapter: return
			filters = []
			for f in filters:
				if f.enabled:
					filters.append(f.dap.id)

			core.run(self.adapter.SetExceptionBreakpoints(filters))

		self.breakpoints = Breakpoints()
		self.breakpoints_for_id = {} #type: Dict[int, Breakpoint]
		self.breakpoints.data.on_send.add(on_send_data_breakpoints)
		self.breakpoints.function.on_send.add(on_send_function_breakpoints)
		self.breakpoints.filters.on_send.add(on_send_filters)
		self.breakpoints.source.on_send.add(self.on_send_source_breakpoint)

		self.state_changed = core.Event() #type: core.Event[int]
		self.modules = Modules()
		self.sources = Sources()
		self.variables = Variables()

		def on_added_watch(expr: Watch.Expression):
			core.run(self.watch.evaluate_expression(self, self.selected_frame, expr))

		self.watch = Watch(on_added_watch)
					
	def dispose_terminals(self):
		for terminal in self.terminals:
			terminal.dispose()

		self.terminals = []
		self.on_terminals(self.terminals)

	def dispose(self) -> None:
		self.force_stop_adapter()
		self.dispose_terminals()
		self.breakpoints.dispose()
		for disposeable in self.disposeables:
			disposeable.dispose()

	@property
	def state(self) -> int:
		return self._state

	@state.setter
	def state(self, state: int) -> None:
		if self._state == state:
			return

		self._state = state
		self.on_state_changed(state)
		self.state_changed()

	def launch(self, adapter_configuration: Adapter, configuration: ConfigurationExpanded, restart: Optional[Any] = None) -> core.awaitable[None]:
		if self.launching_async:
			self.launching_async.cancel()

		self.dispose_terminals()
		self.launching_async = core.run(self._launch(adapter_configuration, configuration, restart))
		try:
			yield from self.launching_async
		except core.Error as e:
			self.launching_async = None
			core.log_exception(e)
			self.error("... an error occured, " + str(e))
			self.force_stop_adapter()
		except core.CancelledError:
			self.launching_async = None
			self.info("... canceled")
			self.force_stop_adapter()

		self.launching_async = None

	def _launch(self, adapter_configuration: Adapter, configuration: ConfigurationExpanded, restart: Optional[Any] = None) -> core.awaitable[None]:
		if self.state != DebuggerStateful.stopped:
			yield from self.stop()

		assert self.state == DebuggerStateful.stopped, "debugger not in stopped state?"
		self.state = DebuggerStateful.starting
		self.adapter_configuration = adapter_configuration
		self.configuration = configuration

		if not adapter_configuration.installed:
			raise core.Error('Debug adapter with type name "{}" is not installed. You can install it by running Debugger: Install Adapters'.format(adapter_configuration.type))

		if 'sublime_debugger_build' in configuration.all:
			self.info('running build...')
			terminal = TerminalStandard('Build Results')
			self.terminals.append(terminal)
			self.on_terminals(self.terminals)
			yield from build.run(sublime.active_window(), terminal.write_stdout, configuration.all['sublime_debugger_build'])
			self.info('... finished running build')

		# dont monitor stdout the StdioTransport uses it
		self.process = Process(adapter_configuration.command, on_stdout=None, on_stderr=self.info)
		transport = StdioTransport(self.process)

		adapter = dap.Client(
			transport,
			self
		)
		self.adapter = adapter

		self.info("starting debugger... ")

		# this is a bit of a weird case. Initialized will happen at some point in time
		# it depends on when the debug adapter chooses it is ready for configuration information
		# when it does happen we can then add all the breakpoints and complete the configuration
		@core.coroutine
		def Initialized() -> core.awaitable[None]:
			try:
				yield from adapter.Initialized()
			except Exception as e:
				self.error("there was waiting for initialized from debugger {}".format(e))
			try:
				yield from self.AddBreakpoints()
			except Exception as e:
				self.error("there was an error adding breakpoints {}".format(e))
			try:
				if self.capabilities.supportsFunctionBreakpoints:
					yield from self.set_function_breakpoints()

				elif len(self.breakpoints.function.breakpoints) > 0:
					self.error("debugger doesn't support function breakpoints")
			except Exception as e:
				self.error("there was an error adding function breakpoints {}".format(e))
			try:
				if self.capabilities.supportsConfigurationDoneRequest:
					yield from adapter.ConfigurationDone()
			except Exception as e:
				self.error("there was an error in configuration done {}".format(e))
		core.run(Initialized())

		self.capabilities = yield from adapter.Initialize()

		filters = self.capabilities.exceptionBreakpointFilters or []
		self.breakpoints.filters.update(filters)

		if configuration.request == 'launch':
			self.launch_request = True
			yield from adapter.Launch(configuration.all, restart)
		elif configuration.request == 'attach':
			self.launch_request = False
			yield from adapter.Attach(configuration.all, restart)
		else:
			raise core.Error('expected configuration to have request of either "launch" or "attach" found {}'.format(configuration.request))

		# get the baseline threads after launch/attach
		# according to https://microsoft.github.io/debug-adapter-protocol/overview
		self.refresh_threads()

		# At this point we are running?
		self.state = DebuggerStateful.running

	def _refresh_state(self) -> None:
		thread = self._selected_or_first_thread()
		if thread and thread.stopped:
			self.state = DebuggerStateful.paused
		else:
			self.state = DebuggerStateful.running
	
	@core.coroutine
	def AddBreakpoints(self) -> core.awaitable[None]:
		assert self.adapter

		requests = [] #type: List[core.awaitable[dict]]

		filters = []
		for filter in self.breakpoints.filters:
			if filter.enabled:
				filters.append(filter.dap.id)

		requests.append(self.adapter.SetExceptionBreakpoints(filters))

		bps = {} #type: Dict[str, List[SourceBreakpoint]]
		for breakpoint in self.breakpoints.source:
			if breakpoint.file in bps:
				bps[breakpoint.file].append(breakpoint)
			else:
				bps[breakpoint.file] = [breakpoint]

		for file, filebreaks in bps.items():
			requests.append(self.on_send_breakpoints_for_file(file, filebreaks))

		if self.capabilities.supportsDataBreakpoints:
			requests.append(self.set_data_breakpoints())

		if requests:
			yield from core.asyncio.wait(requests)

	@core.coroutine
	def set_function_breakpoints(self) -> core.awaitable[None]:
		if not self.adapter:
			return
		breakpoints = list(filter(lambda b: b.enabled, self.breakpoints.function))
		dap_breakpoints = list(map(lambda b: b.dap, breakpoints))
		results = yield from self.adapter.SetFunctionBreakpoints(dap_breakpoints)
		for result, b in zip(results, breakpoints):
			self.breakpoints.function.set_result(b, result)
	
	@core.coroutine
	def set_data_breakpoints(self) -> core.awaitable[None]:
		if not self.adapter: return
		breakpoints = list(filter(lambda b: b.enabled, self.breakpoints.data))
		dap_breakpoints = list(map(lambda b: b.dap, breakpoints))
		results = yield from self.adapter.SetDataBreakpointsRequest(dap_breakpoints)
		for result, b in zip(results, breakpoints):
			self.breakpoints.data.set_result(b, result)

	@core.coroutine
	def on_send_breakpoints_for_file(self, file: str, breakpoints: List[SourceBreakpoint]) -> core.awaitable[None]:
		if not self.adapter:
			return

		enabled_breakpoints = list(filter(lambda b: b.enabled, breakpoints))
		dap_breakpoints = list(map(lambda b: b.dap, enabled_breakpoints))

		try:
			results = yield from self.adapter.SetBreakpointsFile(file, dap_breakpoints)

			if len(results) != len(enabled_breakpoints):
				raise dap.Error(True, 'expected #breakpoints to match results')

			for result, b in zip(results, enabled_breakpoints):
				self.breakpoints.source.set_result(b, result)
				if result.id:
					self.breakpoints_for_id[result.id] = b
		
		except dap.Error as e:
			for b in enabled_breakpoints:
				self.breakpoints.source.set_result(b, dap.BreakpointResult.failed)

	def on_send_source_breakpoint(self, breakpoint: SourceBreakpoint) -> None:
		if not self.adapter:
			return
		file = breakpoint.file
		core.run(self.on_send_breakpoints_for_file(file, self.breakpoints.source.breakpoints_for_file(file)))

	def stop(self) -> core.awaitable[None]:
		# the adapter isn't stopping and stop is called again we force stop it
		if not self.adapter or self.state == DebuggerStateful.stopping:
			self.force_stop_adapter()
			return

		self.state = DebuggerStateful.stopping

		# this seems to be what the spec says to do in the overview
		# https://microsoft.github.io/debug-adapter-protocol/overview
		if self.launch_request:
			if self.capabilities.supportsTerminateRequest:
				try:
					yield from self.adapter.Terminate()
				except dap.Error as e:
					yield from self.adapter.Disconnect()
			else:
				yield from self.adapter.Disconnect()

		else:
			yield from self.adapter.Disconnect()

		self.force_stop_adapter()

	def force_stop_adapter(self) -> None:
		if self.launching_async:
			self.launching_async.cancel()

		self.selected_frame = None
		self.selected_thread_explicitly = False
		self.selected_threadstateful = None

		self.threads_stateful_from_id = {}
		self.threads_stateful = []
		self.breakpoints_for_id = {}

		self.on_threads_stateful(self.threads_stateful)
		self.on_selected_frame(None, None)

		self.variables.clear_session_data()
		self.modules.clear_session_date()
		self.sources.clear_session_date()
		self.breakpoints.clear_session_data()
		self.watch.clear_session_data()

		if self.adapter:
			self.adapter.dispose()
			self.adapter = None
		if self.process:
			self.process.dispose()
			self.process = None
		self.state = DebuggerStateful.stopped

	def require_running(self):
		if not self.adapter:
			raise core.Error('debugger not running')

	@core.coroutine
	def resume(self) -> core.awaitable[None]:
		self.require_running()
		assert self.adapter

		yield from self.adapter.Resume(self._thread_for_command())

	@core.coroutine
	def pause(self) -> core.awaitable[None]:
		self.require_running()
		assert self.adapter

		yield from self.adapter.Pause(self._thread_for_command())

	@core.coroutine
	def step_over(self) -> core.awaitable[None]:
		self.require_running()
		assert self.adapter

		yield from self.adapter.StepOver(self._thread_for_command())
		self.selected_frame = None
		self.selected_thread_explicitly = False

	@core.coroutine
	def step_in(self) -> core.awaitable[None]:
		self.require_running()
		assert self.adapter

		yield from self.adapter.StepIn(self._thread_for_command())
		self.selected_frame = None
		self.selected_thread_explicitly = False

	@core.coroutine
	def step_out(self) -> core.awaitable[None]:
		self.require_running()
		assert self.adapter

		yield from self.adapter.StepOut(self._thread_for_command())
		self.selected_frame = None
		self.selected_thread_explicitly = False

	@core.coroutine
	def evaluate(self, command: str) -> core.awaitable[None]:
		self.info(command)

		self.require_running()
		assert self.adapter

		response = yield from self.adapter.Evaluate(command, self.selected_frame, "repl")
		event = dap.OutputEvent("console", response.result, response.variablesReference)
		self.on_output(event)

	def info(self, string: str) -> None:
		output = dap.OutputEvent("debugger.info", string + '\n', 0)
		self.on_output(output)

	def log_output(self, string: str) -> None:
		output = dap.OutputEvent("debugger.output", string + '\n', 0)
		self.on_output(output)

	def error(self, string: str) -> None:
		output = dap.OutputEvent("debugger.error", string + '\n', 0)
		self.on_output(output)

	# after a successfull launch/attach, stopped event, thread event we request all threads
	# see https://microsoft.github.io/debug-adapter-protocol/overview
	def refresh_threads(self) -> None:
		@core.coroutine
		def refresh_threads() -> core.awaitable[None]:
			threads = yield from self.adapter.GetThreads()
			self._update_threads(threads)
		core.run(refresh_threads())

	def _update_threads(self, threads: List[dap.Thread]) -> None:
		self.threads_stateful = []
		threads_stateful_from_id = {}

		for thread in threads:
			if thread.id in self.threads_stateful_from_id:
				thread_stateful = self.threads_stateful_from_id[thread.id]
				self.threads_stateful.append(thread_stateful)
				thread_stateful.update_name(thread.name)
			
			else:
				thread_stateful = ThreadStateful(self, thread.id, thread.name, self.adapter.allThreadsStopped)
				self.threads_stateful_from_id[thread.id] = thread_stateful
				self.threads_stateful.append(thread_stateful)
			
			threads_stateful_from_id[thread_stateful.id] = thread_stateful

		self.threads_stateful_from_id = threads_stateful_from_id
		self.update_selection_if_needed()
		self.on_threads_stateful(self.threads_stateful)

	def _thread_for_command(self) -> ThreadStateful:
		thread = self._selected_or_first_thread()
		if not thread:
			raise core.Error('No thread to run command')
		return thread

	def _selected_or_first_thread(self) -> Optional[ThreadStateful]:
		if self.selected_threadstateful:
			return self.selected_threadstateful
		if self.threads_stateful:
			return self.threads_stateful[0]
		return None

	def update_selection_if_needed(self, reload_scopes=True) -> None:
		old_frame = self.selected_frame

		# deselect the thread if it has been removed
		if self.selected_threadstateful:
			if not self.selected_threadstateful.id in self.threads_stateful_from_id:
				self.selected_threadstateful = None
				self.selected_frame = None
				self.selected_thread_explicitly = False

		if not self.selected_threadstateful and self.threads_stateful:
			self.selected_threadstateful = self.threads_stateful[0]
			self.selected_threadstateful.expand()

		if not self.selected_frame and self.selected_threadstateful and self.selected_threadstateful.frames:
			self.selected_frame = self.selected_threadstateful.frames[0]

		self.on_threads_stateful(self.threads_stateful)

		if (old_frame is not self.selected_frame) and reload_scopes:
			self.reload_scopes()

	def reload_scopes(self):
		frame = None
		if isinstance(self.selected_frame, dap.StackFrame):
			frame = self.selected_frame
			
		elif isinstance(self.selected_frame, ThreadStateful) and self.selected_frame.frames:
			frame = self.selected_frame.frames[0]
		else:
			self.variables.update(self, [])
			return

		self.on_selected_frame(self.selected_threadstateful, frame)

		core.run(self.get_scopes(frame))
		core.run(self.watch.evaluate(self, self.selected_frame))
	
	@core.coroutine
	def get_scopes(self, frame: dap.StackFrame) -> core.awaitable:
		if not self.adapter: return

		scopes = yield from self.adapter.GetScopes(frame)
		self.variables.update(self, scopes)

	def select_threadstateful(self, thread: ThreadStateful, frame: Optional[dap.StackFrame]):
		self.selected_threadstateful = thread
		self.selected_threadstateful.fetch_if_needed()
		if frame:
			self.selected_frame = frame
			self.selected_thread_explicitly = False
		else:
			self.selected_frame = None
			self.selected_thread_explicitly = True

		self.update_selection_if_needed(reload_scopes=False)
		self.reload_scopes()

	def _threadstateful_for_id(self, id: int) -> ThreadStateful:
		if id in self.threads_stateful_from_id:
			return self.threads_stateful_from_id[id]
		thread = ThreadStateful(self, id, None, self.adapter.allThreadsStopped)
		thread.stopped_text = ""
		return thread

	def on_breakpoint_event(self, event: dap.BreakpointEvent):
		b = self.breakpoints_for_id.get(event.result.id)
		if b:
			self.breakpoints.source.set_result(b, event.result)

	def on_module_event(self, event: dap.ModuleEvent):
		self.modules.on_module_event(event)

	def on_loaded_source_event(self, event: dap.LoadedSourceEvent):
		self.sources.on_loaded_source_event(event)

	def on_output_event(self, event: dap.OutputEvent):
		self.on_output(event)

	def on_threads_event(self, event: dap.ThreadEvent) -> None:
		self.refresh_threads()

	def on_stopped_event(self, event: dap.StoppedEvent):
		self.refresh_threads()

		event_thread = self._threadstateful_for_id(event.threadId)
		event_thread.on_stopped(event.text)
		if event_thread == self.selected_threadstateful:
			self.selected_frame = None
			self.selected_thread_explicitly = False

		if event.allThreadsStopped:
			self.selected_frame = None
			self.selected_thread_explicitly = False
			for thread in self.threads_stateful:
				if event_thread is not thread:
					thread.on_stopped(event.text)

		self._refresh_state()

	def on_continued_event(self, event: dap.ContinuedEvent):
		event_thread = self._threadstateful_for_id(event.threadId)
		event_thread.on_continued()

		if event.allThreadsContinued:
			self.selected_frame = None
			self.selected_thread_explicitly = False
			self.on_selected_frame(None, None)

			for thread in self.threads_stateful:
				if event_thread is not thread:
					thread.on_continued()

		elif event_thread == self.selected_threadstateful:
			self.selected_frame = None
			self.selected_thread_explicitly = False
			self.on_selected_frame(None, None)

		self._refresh_state()

	def on_terminated_event(self, event: dap.TerminatedEvent):
		self.force_stop_adapter()
		if event.restart:
			core.run(self.launch(self.adapter_configuration, self.configuration, event.restart))

	def on_run_in_terminal(self, request: dap.RunInTerminalRequest) -> int: # pid
		terminal = TerminalProcess(request.cwd, request.args)
		self.terminals.append(terminal)
		self.on_terminals(self.terminals)
		return terminal.pid()
