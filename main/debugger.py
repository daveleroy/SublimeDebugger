from sublime_db.core.typecheck import (Tuple, List, Optional, Callable, Union, Dict, Any, Set)
from sublime_db import core

from .breakpoints import (
	Breakpoints,  
	Breakpoint,  
	Filter
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
	CompletionItem
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
		on_state_changed: Callable[[int], None], 
		on_threads: Callable[[List[Thread]], None],
		on_scopes: Callable[[List[Scope]], None],
		on_output: Callable[[OutputEvent], None],
		on_selected_frame: Callable[[Optional[StackFrame]], None]
	) -> None:
		self.on_state_changed = on_state_changed
		self.on_threads = on_threads
		self.on_scopes = on_scopes
		self.on_output = on_output
		self.on_selected_frame = on_selected_frame

		self.adapter = None #type: Optional[DebugAdapterClient]
		self.process = None #type: Optional[Process]

		self.selected_frame = None #type: Optional[StackFrame]
		self.selected_thread = None #type: Optional[Thread]

		self.frame = None #type: Optional[StackFrame]
		self.thread = None #type: Optional[Thread]
		self.threads = []  #type: List[Thread]

		self.stopped_reason = ""

		self._state = DebuggerState.stopped
		self.disposeables = [] #type: List[Any]

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

	def launch(self, adapter_configuration: AdapterConfiguration, configuration: Configuration, breakpoints: Breakpoints) -> core.awaitable[None]:
		if self.state != DebuggerState.stopped:
			print('ignoring launch, not stopped')
			return

		self.state = DebuggerState.starting

		try:
			if not adapter_configuration.installed:
				raise Exception('Debug adapter with type name "{}" is not installed. You can install it by running Debugger: Install Adapters'.format(adapter_configuration.type))

			#If there is a command to run for this debugger run it now
			if adapter_configuration.tcp_port:
				print('Starting Process: {}'.format(adapter_configuration.command))
				try:
					self.process = Process(adapter_configuration.command, 
						on_stdout = self._on_msg, 
						on_stderr = self._on_msg)
				except Exception as e:
					self.on_error('Failed to start debug adapter process: {}'.format(e))
					self.on_error('Command in question: {}'.format(adapter_configuration.command))
					core.display('Failed to start debug adapter process: Check the Event Log for more details')
					self.state = DebuggerState.stopped
					return
				tcp_address = adapter_configuration.tcp_address or 'localhost'
				try:
					transport = yield from start_tcp_transport(tcp_address, adapter_configuration.tcp_port)
				except Exception as e:
					self.on_error('Failed to connect to debug adapter: {}'.format(e))
					self.on_error('address: {} port: {}'.format(tcp_address, adapter_configuration.tcp_port))
					core.display('Failed to connect to debug adapter: Check the Event Log for more details and messages from the debug adapter process?')
					self.state = DebuggerState.stopped
					return
			else:
				# dont monitor stdout the StdioTransport users it
				self.process = Process(adapter_configuration.command, 
						on_stdout = None, 
						on_stderr = self._on_msg)
				
				transport = StdioTransport(self.process)

		except Exception as e:
			core.log_exception()
			core.display(e)
			self.state = DebuggerState.stopped
			return
		
		adapter = DebugAdapterClient(transport)
		adapter.onThreads.add(self._on_threads_event)
		adapter.onOutput.add(self._on_output_event)
		adapter.onStopped.add(self._on_stopped_event)
		adapter.onContinued.add(self._on_continued_event)
		adapter.onExited.add(self._on_exited_event)

		# this is a bit of a weird case. Initialized will happen at some point in time
		# it depends on when the debug adapter chooses it is ready for configuration information
		# when it does happen we can then add all the breakpoints and complete the configuration
		@core.async
		def Initialized() -> core.awaitable[None]:
			yield from adapter.Initialized()
			yield from adapter.AddBreakpoints(breakpoints)
			yield from adapter.ConfigurationDone()
		core.run(Initialized())

		print ('Adapter initialize')
		body = yield from adapter.Initialize()
		for filter in body.get('exceptionBreakpointFilters', []):
			id = filter['filter']
			name = filter['label']
			default = filter.get('default', False)
			breakpoints.add_filter(id, name, default)

		if configuration.request == 'launch':
			yield from adapter.Launch(configuration.all)
		elif configuration.request == 'attach':
			yield from adapter.Attach(configuration.all)
		else:
			raise Exception('expected configuration to have request of either "launch" or "attach" found {}'.format(configuration.request))
		
		print ('Adapter has been launched/attached')
		self.adapter = adapter
		# At this point we are running?
		self.state = DebuggerState.running

	def force_stop_adapter(self) -> None:
		self.selected_frame = None

		self.on_threads([])
		self.on_scopes([])
		self.on_selected_frame(None)

		self.state = DebuggerState.stopped
		if self.adapter:
			self.adapter.dispose()
			self.adapter = None
		if self.process:
			self.process.dispose()
			self.process = None

	def _refresh_state(self) -> None:
		thread = self._thread_for_commands()
		if thread and thread.stopped:
			self.state = DebuggerState.paused
		else:
			self.state = DebuggerState.running

	def update_exception_filters(self, filters: List[Filter]) -> None:
		if self.adapter:
			core.run(self.adapter.setExceptionBreakpoints(filters))

	def update_breakpoints_for_file(self, file: str, breakpoints: List[Breakpoint]) -> None:
		if self.adapter:
			core.run(self.adapter.SetBreakpointsFile(file, breakpoints))

	def stop(self) -> core.awaitable[None]:
		if not self.adapter or self.state == DebuggerState.stopping:
			self.force_stop_adapter()
			return

		self.state = DebuggerState.stopping
		yield from self.adapter.Disconnect()
		self.force_stop_adapter()
	def resume(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		thread = self._thread_for_commands()
		assert thread, 'no thread for command'
		yield from self.adapter.Resume(thread)
	def pause(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		thread = self._thread_for_commands()
		assert thread, 'no thread for command'
		yield from self.adapter.Pause(thread)
	def step_over(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		thread = self._thread_for_commands()
		assert thread, 'no thread for command'
		yield from self.adapter.StepOver(thread)
	def step_in(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		thread = self._thread_for_commands()
		assert thread, 'no thread for command'
		yield from self.adapter.StepIn(thread)
	def step_out(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		thread = self._thread_for_commands()
		assert thread, 'no thread for command'
		yield from self.adapter.StepOut(thread)

	def set_selected_frame(self, frame: Optional[StackFrame]) -> None:
		new_frame = self.thread or self.frame != frame

		self.frame = frame
		self.thread = None

		self.on_selected_frame(frame)

		if new_frame:
			self._refresh_state()
			if self.adapter and frame:
				core.run(self.adapter.GetScopes(frame), self.on_scopes)
			else:
				self.on_scopes([])

	def set_selected_thread(self, thread: Optional[Thread]) -> None:
		new_thread = self.thread != thread
		self.thread = thread
		self.on_selected_frame(self.frame)

		if new_thread:
			self._refresh_state()

	def on_error(self, error: str) -> None:
		output = OutputEvent("stderr", error, 0)
		self.on_output(output)
	def _on_msg(self, message: str) -> None:
		output = OutputEvent("stdout", message, 0)
		self.on_output(output)
	def _on_threads_event(self, threads: Optional[List[Thread]]) -> None:
		self.threads = threads or []
		self.on_threads(threads or [])

	def _on_output_event(self, event: OutputEvent) -> None:
		self.on_output(event)
	def _on_stopped_event(self, event: StoppedEvent) -> None:
		self._refresh_state()
		self.stopped_reason = event.reason
	def _thread_for_commands(self) -> Optional[Thread]:
		if self.thread:
			return self.thread
		if self.frame:
			return self.frame.thread
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
			if self.fetched: self._fetch_if_needed(True)
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