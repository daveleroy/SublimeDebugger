import sublime
from sublime_db.core.typecheck import (Tuple, List, Optional, Callable, Union, Dict, Any, Set)
from sublime_db import core

from .breakpoints import (
	Breakpoints,
	Breakpoint,
	Filter,
	FunctionBreakpoint
)
from .debug_adapter_client.client import (
	DebugAdapterClient,
	StoppedEvent,
	ContinuedEvent,
	OutputEvent
)
from .debug_adapter_client.transport import (
	start_tcp_transport,
	Process,
	TCPTransport,
	StdioTransport
)
from .debug_adapter_client.types import (
	StackFrame,
	EvaluateResponse,
	Thread,
	Scope,
	Variable,
	CompletionItem,
	Error,
	Capabilities,
	ExceptionBreakpointsFilter
)
from .configurations import (
	Configuration,
	AdapterConfiguration
)


class DebuggerState:
	stopped = 0
	paused = 1
	running = 2

	starting = 3
	stopping = 4

	def __init__(self,
			breakpoints: Breakpoints,
			on_state_changed: Callable[[int], None],
			on_threads: Callable[[List[Thread]], None],
			on_scopes: Callable[[List[Scope]], None],
			on_output: Callable[[OutputEvent], None],
			on_selected_frame: Callable[[Optional[Thread], Optional[StackFrame]], None]
		) -> None:
		self.on_state_changed = on_state_changed
		self.on_threads = on_threads
		self.on_scopes = on_scopes
		self.on_output = on_output
		self.on_selected_frame = on_selected_frame

		self.adapter = None #type: Optional[DebugAdapterClient]
		self.process = None #type: Optional[Process]
		self.launching_async = None

		self.launch_request = True

		self.selected_frame = None #type: Optional[StackFrame]
		self.selected_thread = None #type: Optional[Thread]

		self.frame = None #type: Optional[StackFrame]
		self.thread = None #type: Optional[Thread]
		self.threads = []  #type: List[Thread]

		self.stopped_reason = ""

		self._state = DebuggerState.stopped

		self.disposeables = [] #type: List[Any]

		self.breakpoints = breakpoints
		breakpoints.onSendFilterToDebugger.add(self.onSendFilterToDebugger)
		breakpoints.onSendBreakpointToDebugger.add(self.onSendBreakpointToDebugger)
		breakpoints.onSendFunctionBreakpointToDebugger.add(self.onSendFunctionBreakpointToDebugger)


	def dispose(self) -> None:
		self.force_stop_adapter()
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

	def launch(self, adapter_configuration: AdapterConfiguration, configuration: Configuration) -> core.awaitable[None]:
		if self.launching_async:
			self.launching_async.cancel()

		self.launching_async = core.run(self._launch(adapter_configuration, configuration))
		try:
			yield from self.launching_async
		except Exception as e:
			self.launching_async = None
			core.log_exception(e)
			if isinstance(e, core.CancelledError):
				self.log_info("... canceled")
			else:
				self.log_error("... an error occured, " + str(e))
			self.force_stop_adapter()

		self.launching_async = None

	def _launch(self, adapter_configuration: AdapterConfiguration, configuration: Configuration) -> core.awaitable[None]:
		if self.state != DebuggerState.stopped:
			print('stopping debug adapter')
			yield from self.stop()

		assert(self.state == DebuggerState.stopped, "debugger not in stopped state?")
		self.state = DebuggerState.starting
		self.adapter_configuration = adapter_configuration
		self.configuration = configuration

		if not adapter_configuration.installed:
			raise Exception('Debug adapter with type name "{}" is not installed. You can install it by running Debugger: Install Adapters'.format(adapter_configuration.type))


		# If there is a command to run for this debugger run it now
		if adapter_configuration.tcp_port:
			self.log_info('starting debug adapter...')
			try:
				self.process = Process(adapter_configuration.command, on_stdout=self.log_info, on_stderr=self.log_info)
			except Exception as e:
				self.log_error('Failed to start debug adapter process: {}'.format(e))
				self.log_error('Command in question: {}'.format(adapter_configuration.command))
				core.display('Failed to start debug adapter process: Check the Event Log for more details')
				raise Exception("failed to start debug adapter process")
			tcp_address = adapter_configuration.tcp_address or 'localhost'
			try:
				transport = yield from start_tcp_transport(tcp_address, adapter_configuration.tcp_port)
			except Exception as e:
				self.log_error('Failed to connect to debug adapter: {}'.format(e))
				self.log_error('address: {} port: {}'.format(tcp_address, adapter_configuration.tcp_port))
				core.display('Failed to connect to debug adapter: Check the Event Log for more details and messages from the debug adapter process?')
				raise Exception("failed to start debug adapter process")

			self.log_info('... debug adapter started')
		else:
			# dont monitor stdout the StdioTransport users it
			self.process = Process(adapter_configuration.command, on_stdout=None, on_stderr=self.log_info)
			transport = StdioTransport(self.process)

		adapter = DebugAdapterClient(transport)
		adapter.onThreads.add(self._on_threads_event)
		adapter.onOutput.add(self._on_output_event)
		adapter.onStopped.add(self._on_stopped_event)
		adapter.onContinued.add(self._on_continued_event)
		adapter.onExited.add(self._on_exited_event)

		self.log_info("starting debugger... ")

		# this is a bit of a weird case. Initialized will happen at some point in time
		# it depends on when the debug adapter chooses it is ready for configuration information
		# when it does happen we can then add all the breakpoints and complete the configuration
		@core.async
		def Initialized() -> core.awaitable[None]:
			try:
				yield from adapter.Initialized()
			except Exception as e:
				self.log_error("there was waiting for initialized from debugger {}".format(e))
			try:
				yield from adapter.AddBreakpoints(self.breakpoints)
			except Exception as e:
				self.log_error("there was an error adding breakpoints {}".format(e))
			try:
				if capabilities.supportsFunctionBreakpoints:
					yield from adapter.SetFunctionBreakpoints(self.breakpoints.functionBreakpoints)
				elif len(self.breakpoints.functionBreakpoints) > 0:
					self.log_error("debugger doesn't support function breakpoints")
			except Exception as e:
				self.log_error("there was an error adding function breakpoints {}".format(e))
			try:
				if capabilities.supportsConfigurationDoneRequest:
					yield from adapter.ConfigurationDone()
			except Exception as e:
				self.log_error("there was an error in configuration done {}".format(e))
		core.run(Initialized())

		capabilities = yield from adapter.Initialize()
		for filter in capabilities.exceptionBreakpointFilters:
			self.breakpoints.add_filter(filter.id, filter.label, filter.default)

		if configuration.request == 'launch':
			self.launch_request = True
			yield from adapter.Launch(configuration.all)
		elif configuration.request == 'attach':
			self.launch_request = False
			yield from adapter.Attach(configuration.all)
		else:
			raise Exception('expected configuration to have request of either "launch" or "attach" found {}'.format(configuration.request))

		self.adapter = adapter
		# At this point we are running?
		self.state = DebuggerState.running

	def force_stop_adapter(self) -> None:
		if self.launching_async:
			self.launching_async.cancel()

		self.selected_frame = None
		self.on_threads([])
		self.on_scopes([])
		self.on_selected_frame(None, None)
		if self.adapter:
			self.adapter.dispose()
			self.adapter = None
		if self.process:
			self.process.dispose()
			self.process = None
		self.state = DebuggerState.stopped

	def _refresh_state(self) -> None:
		thread = self._selected_or_first_thread()
		if thread and thread.stopped:
			self.state = DebuggerState.paused
		else:
			self.state = DebuggerState.running

	def onSendFilterToDebugger(self, filter: Filter) -> None:
		if not self.adapter:
			return
		core.run(self.adapter.setExceptionBreakpoints(self.breakpoints.filters))

	def onSendBreakpointToDebugger(self, breakpoint: Breakpoint) -> None:
		if not self.adapter:
			return
		file = breakpoint.file
		breakpoints = self.breakpoints.breakpoints_for_file(file)
		core.run(self.adapter.SetBreakpointsFile(file, breakpoints))

	def onSendFunctionBreakpointToDebugger(self, breakpoint: FunctionBreakpoint) -> None:
		pass

	def stop(self) -> core.awaitable[None]:
		# the adapter isn't stopping and stop is called again we force stop it
		if not self.adapter or self.state == DebuggerState.stopping:
			self.force_stop_adapter()
			return

		self.state = DebuggerState.stopping

		# this seems to be what the spec says to do in the overview
		# https://microsoft.github.io/debug-adapter-protocol/overview
		if self.launch_request:
			try:
				yield from self.adapter.Terminate()
			except Error as e:
				yield from self.adapter.Disconnect()
		else:
			yield from self.adapter.Disconnect()

		self.force_stop_adapter()

	def resume(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		yield from self.adapter.Resume(self._thread_for_command())

	def pause(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		yield from self.adapter.Pause(self._thread_for_command())

	def step_over(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		yield from self.adapter.StepOver(self._thread_for_command())

	def step_in(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		yield from self.adapter.StepIn(self._thread_for_command())

	def step_out(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		yield from self.adapter.StepOut(self._thread_for_command())

	def set_selected_frame(self, frame: Optional[StackFrame]) -> None:
		new_frame = self.frame != frame
		self.frame = frame
		if new_frame:
			self.on_selected_frame(self.thread, frame)
			self._refresh_state()
			if self.adapter and frame:
				core.run(self.adapter.GetScopes(frame), self.on_scopes)
			else:
				self.on_scopes([])

	def set_selected_thread(self, thread: Optional[Thread]) -> None:
		new_thread = self.thread != thread
		self.thread = thread
		if new_thread:
			self._refresh_state()

	def log_info(self, string: str) -> None:
		output = OutputEvent("info", string, 0)
		self.on_output(output)

	def log_output(self, string: str) -> None:
		output = OutputEvent("output", string, 0)
		self.on_output(output)

	def log_error(self, string: str) -> None:
		output = OutputEvent("error", string, 0)
		self.on_output(output)
	
	def evaluate(self, command: str):
		self.log_info(command)

		adapter = self.adapter

		if not adapter:
			self.log_error("Failed to run command: Debugger is not running")
			return

		@core.async
		def run():
			try:
				response = yield from adapter.Evaluate(command, self.frame, "repl")
			except Exception as e:
				self.log_error(str(e))
				return

			event = OutputEvent("console", response.result, response.variablesReference)
			self.on_output(event)
		core.run(run())

	def _unselect_thread_if_not_found(self) -> None:
		for thread in self.threads:
			if thread == self.thread:
				return
		self.set_selected_thread(None)
		self.set_selected_frame(None)

	def _on_threads_event(self, threads: Optional[List[Thread]]) -> None:
		self.threads = threads or []
		self._unselect_thread_if_not_found()
		self.on_threads(threads or [])

	def _on_output_event(self, event: OutputEvent) -> None:
		self.on_output(event)

	def _on_stopped_event(self, event: StoppedEvent) -> None:
		self._refresh_state()
		self.stopped_reason = event.reason

	def _thread_for_command(self) -> Thread:
		thread = self._selected_or_first_thread()
		if not thread:
			raise Exception('No thread to run command')
		return thread

	def _selected_or_first_thread(self) -> Optional[Thread]:
		if self.thread:
			return self.thread
		if self.threads:
			return self.threads[0]
		return None

	def _on_continued_event(self, event: ContinuedEvent) -> None:
		if not event:
			return

		if event.allThreadsContinued:
			self.set_selected_thread(None)
			self.set_selected_frame(None)
		else:
			if self.thread and self.thread == event.thread:
				self.set_selected_thread(None)
			if self.frame and self.frame.thread == event.thread:
				self.set_selected_frame(None)

		self._refresh_state()

	def _on_exited_event(self, event: Any) -> None:
		self.force_stop_adapter()


class VariableState:
	def __init__(self, variable: Variable, on_updated: Callable[[], None]) -> None:
		self.variable = variable
		self.on_updated = on_updated

		self._expanded = False
		self.fetched = False
		self.loading = False
		self.variables = [] #type: List[Variable]

	@property
	def name(self) -> str:
		return self.variable.name

	@property
	def value(self) -> str:
		return self.variable.value

	@property
	def expanded(self) -> bool:
		return self._expanded

	@property
	def expandable(self) -> bool:
		return self.variable.variablesReference != 0

	def toggle_expand(self) -> None:
		if self._expanded:
			self._expanded = False
		else:
			self._expanded = True
			self._fetch_if_needed()
		self.on_updated()

	def expand(self) -> None:
		if not self._expanded:
			self.toggle_expand()

	def collapse(self) -> None:
		if self._expanded:
			self.toggle_expand()

	@core.async
	def _set_value(self, value: str) -> core.awaitable[None]:
		try:
			variable = yield from self.variable.client.setVariable(self.variable, value)
			self.variable = variable
			if self.fetched:
				self._fetch_if_needed(True)
			self.on_updated()
		except Exception as e:
			core.log_exception()
			core.display(e)

	def set_value(self, value: str) -> None:
		core.run(self._set_value(value))

	def _fetch_if_needed(self, force_refetch: bool = False) -> None:
		if (not self.fetched or force_refetch) and self.variable.variablesReference:
			self.loading = True
			core.run(self.variable.client.GetVariables(self.variable.variablesReference), self._on_fetched)

	def _on_fetched(self, variables: List[Variable]) -> None:
		self.fetched = True
		self.loading = False
		self.variables = variables
		self.on_updated()


class ScopeState:
	def __init__(self, scope: Scope, on_updated: Callable[[], None]) -> None:
		self.scope = scope
		self.on_updated = on_updated

		self._expanded = False
		self.fetched = False
		self.loading = False
		self.variables = [] #type: List[Variable]

	@property
	def name(self) -> str:
		return self.scope.name

	@property
	def expanded(self) -> bool:
		return self._expanded

	@property
	def expensive(self):
		return self.scope.expensive

	def toggle_expand(self) -> None:
		if self._expanded:
			self._expanded = False
		else:
			self._expanded = True
			self._fetch_if_needed()
		self.on_updated()

	def expand(self) -> None:
		if not self._expanded:
			self.toggle_expand()

	def collapse(self) -> None:
		if self._expanded:
			self.toggle_expand()

	def _fetch_if_needed(self) -> None:
		if not self.fetched and self.scope.variablesReference:
			self.loading = True
			core.run(self.scope.client.GetVariables(self.scope.variablesReference), self._on_fetched)

	def _on_fetched(self, variables: List[Variable]) -> None:
		self.fetched = True
		self.loading = False
		self.variables = variables
		self.on_updated()


class ThreadState:
	def __init__(self, thread: Thread, on_updated: Callable[[], None]) -> None:
		self.thread = thread
		self.on_updated = on_updated

		self._expanded = False
		self.fetched = False
		self.loading = False
		self.frames = [] #type: List[StackFrame]

	@property
	def name(self) -> str:
		return self.thread.name

	@property
	def stopped(self) -> bool:
		return self.thread.stopped

	@property
	def expanded(self) -> bool:
		return self._expanded

	@property
	def expandable(self) -> bool:
		return self.thread.stopped

	def toggle_expand(self) -> None:
		if self._expanded:
			self._expanded = False
		else:
			self._expanded = True
			self._fetch_if_needed()
		self.on_updated()

	def expand(self) -> None:
		if not self._expanded:
			self.toggle_expand()

	def collapse(self) -> None:
		if self._expanded:
			self.toggle_expand()

	def _fetch_if_needed(self, force_refetch: bool = False) -> None:
		if (not self.fetched or force_refetch) and self.thread.stopped:
			self.loading = True
			core.run(self.thread.client.GetStackTrace(self.thread), self._on_fetched)

	def _on_fetched(self, frames: List[StackFrame]) -> None:
		self.fetched = True
		self.loading = False
		self.frames = frames
		self.on_updated()
