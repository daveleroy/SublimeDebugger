from sublime_db.modules.core.typecheck import (Tuple, List, Optional, Callable, Union, Dict, Any, Set)

import sublime
from sublime_db.modules import core

from sublime_db.modules.dap.client import (
	DebugAdapterClient,
	StoppedEvent,
	ContinuedEvent,
	OutputEvent
)
from sublime_db.modules.dap.transport import (
	start_tcp_transport,
	Process,
	TCPTransport,
	StdioTransport
)
from sublime_db.modules.dap.types import (
	StackFrame,
	EvaluateResponse,
	Thread,
	Scope,
	Variable,
	CompletionItem,
	Error,
	Capabilities,
	ExceptionBreakpointsFilter,
	Source,
	ThreadEvent
)
from .adapter_configuration import (
	Configuration,
	AdapterConfiguration
)
from .breakpoints import (
	Breakpoints,
	Breakpoint,
	Filter,
	FunctionBreakpoint
)
from .thread import (
	ThreadStateful
)


class DebuggerStateful:
	stopped = 0
	paused = 1
	running = 2

	starting = 3
	stopping = 4

	def __init__(self,
			breakpoints: Breakpoints,
			on_state_changed: Callable[[int], None],
			on_scopes: Callable[[List[Scope]], None],
			on_output: Callable[[OutputEvent], None],
			on_selected_frame: Callable[[Optional[Thread], Optional[StackFrame]], None],
			on_threads_stateful: Callable[[List[ThreadStateful]], None],
		) -> None:
		self.on_state_changed = on_state_changed
		self.on_threads_stateful = on_threads_stateful
		self.on_scopes = on_scopes
		self.on_output = on_output
		self.on_selected_frame = on_selected_frame

		self.adapter = None #type: Optional[DebugAdapterClient]
		self.process = None #type: Optional[Process]
		self.launching_async = None

		self.launch_request = True
		self.supports_terminate_request = True

		self.selected_frame = None #type: Optional[StackFrame]
		self.selected_thread = None #type: Optional[Thread]
		self.selected_threadstateful = None #type: Optional[Thread]

		self.frame = None #type: Optional[StackFrame]
		self.threads_stateful = []
		self.threads_stateful_from_id = {}

		self._state = DebuggerStateful.stopped

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
		if self.state != DebuggerStateful.stopped:
			print('stopping debug adapter')
			yield from self.stop()

		assert(self.state == DebuggerStateful.stopped, "debugger not in stopped state?")
		self.state = DebuggerStateful.starting
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
		self.supports_terminate_request = capabilities.supportTerminateDebuggee

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

		# get the baseline threads after launch/attach
		# according to https://microsoft.github.io/debug-adapter-protocol/overview
		self.refresh_threads()

		self.adapter = adapter
		# At this point we are running?
		self.state = DebuggerStateful.running

	def force_stop_adapter(self) -> None:
		if self.launching_async:
			self.launching_async.cancel()

		self.selected_frame = None
		self.selected_threadstateful = None

		self.threads_stateful_from_id = {}
		self.threads_stateful = []
		self.on_threads_stateful(self.threads_stateful)
		self.on_scopes([])
		self.on_selected_frame(None, None)
		if self.adapter:
			self.adapter.dispose()
			self.adapter = None
		if self.process:
			self.process.dispose()
			self.process = None
		self.state = DebuggerStateful.stopped

	def _refresh_state(self) -> None:
		thread = self._selected_or_first_thread()
		if thread and thread.stopped:
			self.state = DebuggerStateful.paused
		else:
			self.state = DebuggerStateful.running

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
		if not self.adapter or self.state == DebuggerStateful.stopping:
			self.force_stop_adapter()
			return

		self.state = DebuggerStateful.stopping

		# this seems to be what the spec says to do in the overview
		# https://microsoft.github.io/debug-adapter-protocol/overview
		if self.launch_request:
			if self.supports_terminate_request:
				try:
					yield from self.adapter.Terminate()
				except Error as e:
					yield from self.adapter.Disconnect()
			else:
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
		self.selected_frame = None

	def step_in(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		yield from self.adapter.StepIn(self._thread_for_command())
		self.selected_frame = None

	def step_out(self) -> core.awaitable[None]:
		assert self.adapter, 'no adapter for command'
		yield from self.adapter.StepOut(self._thread_for_command())
		self.selected_frame = None

	def log_info(self, string: str) -> None:
		output = OutputEvent("debugger.info", string, 0)
		self.on_output(output)

	def log_output(self, string: str) -> None:
		output = OutputEvent("debugger.output", string, 0)
		self.on_output(output)

	def log_error(self, string: str) -> None:
		output = OutputEvent("debugger.error", string, 0)
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


	# after a successfull launch/attach, stopped event, thread event we request all threads
	# see https://microsoft.github.io/debug-adapter-protocol/overview
	def refresh_threads(self) -> None:
		@core.async
		def async() -> core.awaitable[None]:
			threads = yield from self.adapter.GetThreads()
			self._update_threads(threads)
		core.run(async())

	def _update_threads(self, threads: Optional[List[Thread]]) -> None:
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

	def _on_threads_event(self, event: ThreadEvent) -> None:
		self.refresh_threads()

	def _on_output_event(self, event: OutputEvent) -> None:
		self.on_output(event)

	def _thread_for_command(self) -> ThreadStateful:
		thread = self._selected_or_first_thread()
		if not thread:
			raise Exception('No thread to run command')
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

		if not self.selected_threadstateful and self.threads_stateful:
			self.selected_threadstateful = self.threads_stateful[0]
			self.selected_threadstateful.expand()

		if not self.selected_frame and self.selected_threadstateful and self.selected_threadstateful.frames:
			self.selected_frame = self.selected_threadstateful.frames[0]

		self.on_threads_stateful(self.threads_stateful)

		if old_frame != self.selected_frame and reload_scopes:
			self.reload_scopes()

	def reload_scopes(self):
		frame = None
		if isinstance(self.selected_frame, StackFrame):
			frame = self.selected_frame
			
		elif isinstance(self.selected_frame, ThreadStateful) and self.selected_frame.frames:
			frame = self.selected_frame.frames[0]
		else:
			self.on_scopes([])
			return

		core.run(self.adapter.GetScopes(frame), self.on_scopes)
		self.on_selected_frame(self.selected_threadstateful, frame)

	def select_threadstateful(self, thread: ThreadStateful, frame: Optional[StackFrame]):
		self.selected_threadstateful = thread
		self.selected_threadstateful.fetch_if_needed()
		if frame:
			self.selected_frame = frame
		else:
			self.selected_frame = thread

		self.update_selection_if_needed(reload_scopes=False)
		self.reload_scopes()

	def _threadstateful_for_id(self, id: int) -> ThreadStateful:
		if id in self.threads_stateful_from_id:
			return self.threads_stateful_from_id[id]
		thread = ThreadStateful(self, id, None, self.adapter.allThreadsStopped)
		return thread

	def _on_continued_event(self, event: ContinuedEvent) -> None:
		if not event:
			return

		thread = self._threadstateful_for_id(event.threadId).on_continued()
		if thread == self.selected_threadstateful:
			self.selected_frame = None

		if event.allThreadsContinued:
			self.selected_frame = None

			for thread in self.threads_stateful:
				thread.on_continued()

		self._refresh_state()
	
	def _on_stopped_event(self, event: StoppedEvent) -> None:
		self.refresh_threads()

		thread = self._threadstateful_for_id(event.threadId).on_stopped(event.text)
		if thread == self.selected_threadstateful:
			self.selected_frame = None

		if event.allThreadsStopped:
			self.selected_frame = None
			for thread in self.threads_stateful:
				thread.on_stopped(event.text)

		self.update_selection_if_needed()
		self._refresh_state()

	def _on_exited_event(self, event: Any) -> None:
		self.force_stop_adapter()

