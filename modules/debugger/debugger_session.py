from __future__ import annotations
from ..typecheck import *

from ..import core, dap

from .terminals import (
	Terminal, 
	TerminalCommand,
)
from .adapter import (
	ConfigurationExpanded,
	Adapter
)
from .breakpoints import (
	Breakpoints,
	SourceBreakpoint,
)

from .variables import Variables, Variable, ScopeReference
from .watch import Watch
from .debugger_terminals import Terminals

import sublime

class DebuggerSession(dap.ClientEventsListener, core.Logger):
	stopped = 0
	paused = 1
	running = 2

	starting = 3
	stopping = 4	

	stopped_reason_build_failed=0
	stopped_reason_launch_error=1
	stopped_reason_dispose=2
	stopped_reason_cancel=3
	stopped_reason_terminated_event=4
	stopped_reason_manual=5

	def __init__(
		self,
		breakpoints: Breakpoints,
		watch: Watch,
		terminals: Terminals,
		on_state_changed: Callable[[int], None],
		on_output: Callable[[dap.OutputEvent], None],
		on_selected_frame: Callable[[Optional[dap.StackFrame]], None],
		transport_log: core.Logger,
	) -> None:

		self.on_selected_frame = on_selected_frame

		self.transport_log = transport_log
		self.state_changed = core.Event() #type: core.Event[int]

		self.terminals = terminals
		self.terminals_updated = core.Event() #type: core.Event[None]

		self.breakpoints = breakpoints
		self.breakpoints_for_id = {} #type: Dict[int, SourceBreakpoint]
		self.breakpoints.data.on_send.add(self.on_send_data_breakpoints)
		self.breakpoints.function.on_send.add(self.on_send_function_breakpoints)
		self.breakpoints.filters.on_send.add(self.on_send_filters)
		self.breakpoints.source.on_send.add(self.on_send_source_breakpoint)

		self.watch = watch
		self.watch.on_added.add(lambda expr: self.watch.evaluate_expression(self, self.selected_frame, expr))
		self.on_state_changed = on_state_changed
		self.on_output = on_output

		self.adapter = None #type: Optional[dap.Client]
		self.launching_async = None #type: Optional[core.future]
		self.capabilities = None
		self.stop_requested = False
		self.launch_request = True
		self._state = DebuggerSession.stopped

		self.disposeables = [] #type: List[Any]

		self.complete = core.future()

		self.threads_for_id: Dict[int, Thread] = {}
		self.all_threads_stopped = False
		self.selected_explicitly = False
		self.selected_thread = None
		self.selected_frame = None

		self.threads: List[Thread] = []
		self.variables: List[Variable] = []
		self.sources: Dict[dap.Source] = {}
		self.modules: Dict[dap.Module] = {}

		self.on_updated_threads = core.Event()
		self.on_threads_selected: core.Event[Optional[Thread], Optional[dap.StackFrame]] = core.Event()
		self.on_threads_selected.add(lambda thread, frame: self.load_frame(frame))

		self.on_updated_modules = core.Event()
		self.on_updated_sources = core.Event()
		self.on_updated_variables = core.Event()

	@property
	def name(self) -> str:
		return self.configuration.name

	def dispose_terminals(self):
		self.terminals.clear_session_data(self)

	def dispose(self) -> None:
		self.clear_session()
		self.dispose_terminals()
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
		self.on_state_changed(self, state)
		self.state_changed()

	async def launch(self, adapter_configuration: Adapter, configuration: ConfigurationExpanded, restart: Optional[Any] = None, no_debug: bool = False) -> None:
		self.dispose_terminals()
		try:
			self.launching_async = core.run(self._launch(adapter_configuration, configuration, restart, no_debug))
			await self.launching_async
		except core.Error as e:
			self.launching_async = None
			core.log_exception(e)
			self.error("... an error occured, " + str(e))
			await self.stop_forced(reason=DebuggerSession.stopped_reason_launch_error)

		except core.CancelledError:
			self.launching_async = None
			self.info("... launch aborted")
			await self.stop_forced(reason=DebuggerSession.stopped_reason_cancel)

		self.launching_async = None

	async def _launch(self, adapter_configuration: Adapter, configuration: ConfigurationExpanded, restart: Optional[Any], no_debug: bool) -> None:
		if self.state != DebuggerSession.stopped:
			await self.stop()
			return
		configuration = adapter_configuration.configuration_resolve(configuration)

		assert self.state == DebuggerSession.stopped, "debugger not in stopped state?"
		self.state = DebuggerSession.starting
		self.adapter_configuration = adapter_configuration
		self.configuration = configuration

		if not adapter_configuration.installed_version:
			raise core.Error('Debug adapter with type name "{}" is not installed. You can install it by running Debugger: Install Adapters'.format(adapter_configuration.type))

		if not await self.run_pre_debug_task():
			await self.stop_forced(reason=DebuggerSession.stopped_reason_build_failed)
			return

		try:
			transport = await adapter_configuration.start(log=self)
		except Exception as e:
			raise core.Error(f"Unable to start the adapter process: {e}")

		adapter = dap.Client(
			transport,
			self,
			self.transport_log
		)
		self.adapter = adapter

		self.info("starting debugger... ")

		# this is a bit of a weird case. Initialized will happen at some point in time
		# it depends on when the debug adapter chooses it is ready for configuration information
		# when it does happen we can then add all the breakpoints and complete the configuration
		async def Initialized() -> None:
			try:
				await adapter.Initialized()
			except core.Error as e:
				self.error("there was waiting for initialized from debugger {}".format(e))

			try:
				await self.add_breakpoints()
			except core.Error as e:
				self.error("there was an error adding breakpoints {}".format(e))

			try:
				if self.capabilities.supportsConfigurationDoneRequest:
					await adapter.ConfigurationDone()
			except core.Error as e:
				self.error("there was an error in configuration done {}".format(e))
		core.run(Initialized())

		self.capabilities = await adapter.Initialize()
		# remove/add any exception breakpoint filters
		self.breakpoints.filters.update(self.capabilities.exceptionBreakpointFilters or [])

		if configuration.request == 'launch':
			self.launch_request = True
			await adapter.Launch(configuration, restart, no_debug)
		elif configuration.request == 'attach':
			self.launch_request = False
			await adapter.Attach(configuration, restart, no_debug)
		else:
			raise core.Error('expected configuration to have request of either "launch" or "attach" found {}'.format(configuration.request))

		# get the baseline threads after launch/attach
		# according to https://microsoft.github.io/debug-adapter-protocol/overview
		self.refresh_threads()

		# At this point we are running?
		self.state = DebuggerSession.running

	async def wait(self) -> None:
		await self.complete

	async def run_pre_debug_task(self) -> bool:
		pre_debug_command = self.configuration.all.get('pre_debug_command')
		if pre_debug_command:
			self.info('running pre debug command...')
			return await self.run_task(pre_debug_command)
		return True

	async def run_post_debug_task(self) -> bool:
		post_debug_command = self.configuration.all.get('post_debug_command')
		if post_debug_command:
			self.info('running post debug command...')
			return await self.run_task(post_debug_command)
		return True

	async def run_task(self, args: Dict[str, Any]) -> bool:
		try:
			terminal = TerminalCommand(args)
			if not terminal.background:
				self.terminals.add(self, terminal)
			await terminal.wait()
			self.info('... finished')
			return True
		except Exception as e:
			core.log_exception()
			self.error(f'... failed: {e}')
			return False

	def _refresh_state(self) -> None:
		try:
			thread = self.command_thread
			if thread.stopped:
				self.state = DebuggerSession.paused
			else:
				self.state = DebuggerSession.running

		except core.Error as e:
			self.state = DebuggerSession.running

	async def add_breakpoints(self) -> None:
		assert self.adapter

		requests = [] #type: List[Awaitable[Any]]

		requests.append(self.set_exception_breakpoint_filters())
		requests.append(self.set_function_breakpoints())

		bps = {} #type: Dict[str, List[SourceBreakpoint]]
		for breakpoint in self.breakpoints.source:
			if breakpoint.file in bps:
				bps[breakpoint.file].append(breakpoint)
			else:
				bps[breakpoint.file] = [breakpoint]

		for file, filebreaks in bps.items():
			requests.append(self.set_breakpoints_for_file(file, filebreaks))

		if self.capabilities.supportsDataBreakpoints:
			requests.append(self.set_data_breakpoints())

		if requests:
			await core.wait(requests)

	async def set_exception_breakpoint_filters(self) -> None:
		if not self.adapter:
			return
		filters = [] #type: List[str]
		for f in self.breakpoints.filters:
			if f.enabled:
				filters.append(f.dap.id)

		await self.adapter.SetExceptionBreakpoints(filters)

	async def set_function_breakpoints(self) -> None:
		if not self.adapter:
			return
		breakpoints = list(filter(lambda b: b.enabled, self.breakpoints.function))

		if not self.capabilities.supportsFunctionBreakpoints:
			# only show error message if the user tried to set a function breakpoint when they are not supported
			if breakpoints:
				self.error("This debugger doesn't support function breakpoints")
			return

		dap_breakpoints = list(map(lambda b: b.dap, breakpoints))
		results = await self.adapter.SetFunctionBreakpoints(dap_breakpoints)
		for result, b in zip(results, breakpoints):
			self.breakpoints.function.set_result(b, result)

	async def set_data_breakpoints(self) -> None:
		if not self.adapter:
			return
		breakpoints = list(filter(lambda b: b.enabled, self.breakpoints.data))
		dap_breakpoints = list(map(lambda b: b.dap, breakpoints))
		results = await self.adapter.SetDataBreakpointsRequest(dap_breakpoints)
		for result, b in zip(results, breakpoints):
			self.breakpoints.data.set_result(b, result)

	async def set_breakpoints_for_file(self, file: str, breakpoints: List[SourceBreakpoint]) -> None:
		if not self.adapter:
			return

		enabled_breakpoints = list(filter(lambda b: b.enabled, breakpoints))
		dap_breakpoints = list(map(lambda b: b.dap, enabled_breakpoints))

		try:
			results = await self.adapter.SetBreakpointsFile(file, dap_breakpoints)

			if len(results) != len(enabled_breakpoints):
				raise dap.Error(True, 'expected #breakpoints to match results')

			for result, b in zip(results, enabled_breakpoints):
				self.breakpoints.source.set_result(b, result)
				if result.id:
					self.breakpoints_for_id[result.id] = b

		except dap.Error as e:
			for b in enabled_breakpoints:
				self.breakpoints.source.set_result(b, dap.BreakpointResult.failed)

	def on_send_data_breakpoints(self, any):
		core.run(self.set_data_breakpoints())

	def on_send_function_breakpoints(self, any):
		core.run(self.set_function_breakpoints())

	def on_send_filters(self, any):
		core.run(self.set_exception_breakpoint_filters())

	def on_send_source_breakpoint(self, breakpoint: SourceBreakpoint) -> None:
		file = breakpoint.file
		core.run(self.set_breakpoints_for_file(file, self.breakpoints.source.breakpoints_for_file(file)))

	async def stop(self):
		# this seems to be what the spec says to do in the overview
		# https://microsoft.github.io/debug-adapter-protocol/overview

		# If the stop is called multiple times then we call disconnect to forefully disconnect
		if self.stop_requested:
			await self.stop_forced(reason=DebuggerSession.stopped_reason_manual)
			return

		self.stop_requested = True

		if self.launch_request:
			if self.capabilities and self.capabilities.supportsTerminateRequest:
				try:
					await self.client.Terminate()
				except dap.Error as e:
					await self.client.Disconnect()
			else:
				await self.client.Disconnect()

		else:
			await self.client.Disconnect()

		
	def clear_session(self):
		if self.launching_async:
			self.launching_async.cancel()

		self.breakpoints_for_id = {}

		self.watch.clear_session_data(self)
		self.breakpoints.clear_session_data()

		self.stop_requested = False

		if self.adapter:
			self.adapter.dispose()
			self.adapter = None

			
	async def stop_forced(self, reason) -> None:
		if self.state == DebuggerSession.stopping or self.state == DebuggerSession.stopped:
			return

		self.stopped_reason = reason
		self.state = DebuggerSession.stopping
		self.clear_session()
		await self.run_post_debug_task()
		self.state = DebuggerSession.stopped

		if not self.complete.done():
			self.complete.set_result(None)

	@property
	def client(self) -> dap.Client:
		if not self.adapter:
			raise core.Error('debugger not running')
		return self.adapter

	async def resume(self):
		await self.client.Resume(self.command_thread)

	async def pause(self):
		await self.client.Pause(self.command_thread)

	async def step_over(self):
		await self.client.StepOver(self.command_thread)

	async def step_in(self):
		await self.client.StepIn(self.command_thread)

	async def step_out(self):
		await self.client.StepOut(self.command_thread)

	async def evaluate(self, command: str):
		self.info(command)
		response = await self.client.Evaluate(command, self.selected_frame, "repl")
		event = dap.OutputEvent("console", response.result, response.variablesReference)
		self.on_output(self, event)

	async def stack_trace(self, thread_id: str) -> List[dap.StackFrame]:
		return await self.client.StackTrace(thread_id)

	async def completions(self, text: str, column: int) -> List[dap.StackFrame]:
		return await self.client.Completions(text, column, self.selected_frame)

	def log_output(self, string: str) -> None:
		output = dap.OutputEvent("debugger.output", string + '\n', 0)
		self.on_output(self, output)

	def info(self, string: str) -> None:
		output = dap.OutputEvent("debugger.info", string + '\n', 0)
		self.on_output(self, output)

	def error(self, string: str) -> None:
		output = dap.OutputEvent("debugger.error", string + '\n', 0)
		self.on_output(self, output)

	def load_frame(self, frame: Optional[dap.StackFrame]):
		self.on_selected_frame(self, frame)
		if frame:
			core.run(self.get_scopes(frame))
			core.run(self.watch.evaluate(self, self.selected_frame))
		else:
			self.variables.clear()
			self.on_updated_variables()

	async def get_scopes(self, frame: dap.StackFrame):
		scopes = await self.client.GetScopes(frame)
		self.variables = [Variable(self, ScopeReference(scope)) for scope in scopes]
		self.on_updated_variables()
		
	def on_breakpoint_event(self, event: dap.BreakpointEvent):
		b = self.breakpoints_for_id.get(event.result.id)
		if b:
			self.breakpoints.source.set_result(b, event.result)

	def on_module_event(self, event: dap.ModuleEvent):
		if event.reason == dap.ModuleEvent.new:
			self.modules[event.module.id] = event.module

		if event.reason == dap.ModuleEvent.removed:
			try:
				del self.modules[event.module.id]
			except KeyError:
				...
		if event.reason == dap.ModuleEvent.changed:
			self.modules[event.module.id] = event.module

		self.on_updated_modules()

	def on_loaded_source_event(self, event: dap.LoadedSourceEvent):
		if event.reason == dap.LoadedSourceEvent.new:
			self.sources[event.source.id] = event.source

		elif event.reason == dap.LoadedSourceEvent.removed:
			try:
				del self.sources[event.source.id]
			except KeyError:
				...
		elif event.reason == dap.LoadedSourceEvent.changed:
			self.sources[event.source.id] = event.source

		self.on_updated_sources()

	def on_output_event(self, event: dap.OutputEvent):
		self.on_output(self, event)

	def on_terminated_event(self, event: dap.TerminatedEvent):
		async def on_terminated_async():
			await self.stop_forced(reason=DebuggerSession.stopped_reason_terminated_event)
			# restarting needs to be handled by creating a new session
			# if event.restart:
			# 	await self.launch(self.adapter_configuration, self.configuration, event.restart)

		core.run(on_terminated_async())

	def on_run_in_terminal(self, request: dap.RunInTerminalRequest) -> dap.RunInTerminalResponse:
		try:
			return self.terminals.on_terminal_request(self, request)
		except core.Error as e:
			self.error(str(e))
			raise e

	@property
	def command_thread(self) -> Thread:
		if self.selected_thread:
			return self.selected_thread
		if self.threads:
			return self.threads[0]

		raise core.Error("No threads to run command")

	def get_thread(self, id: int):
		t = self.threads_for_id.get(id)
		if t:
			return t
		else:
			t = Thread(self, id, "??", self.all_threads_stopped)
			self.threads_for_id[id] = t
			return t

	def set_selected(self, thread: Thread, frame: Optional[dap.StackFrame]):
		self.selected_explicitly = True
		self.selected_thread = thread
		self.selected_frame = frame
		self.on_updated_threads()
		self.on_threads_selected(thread, frame)
		self._refresh_state()

	def on_threads_event(self, event: dap.ThreadEvent) -> None:
		self.refresh_threads()

	def on_stopped_event(self, stopped: dap.StoppedEvent):
		if stopped.allThreadsStopped:
			self.all_threads_stopped = True

			for thread in self.threads:
				thread.clear()
				thread.stopped = True

		# @NOTE this thread might be new and not in self.threads so we must update its state explicitly
		thread = self.get_thread(stopped.threadId)
		thread.clear()
		thread.stopped = True
		thread.stopped_reason = stopped.text

		if not self.selected_explicitly:
			self.selected_thread = thread
			self.selected_frame = None

			self.on_threads_selected(thread, None)

			@core.schedule
			async def run(thread=thread):
				children = await thread.children()
				if children and not self.selected_frame and not self.selected_explicitly and self.selected_thread is thread:
					def first_non_subtle_frame(frames: List[dap.StackFrame]):
						for frame in frames:
							if frame.presentation != dap.StackFrame.subtle:
								return frame
						return frames[0]

					self.selected_frame = first_non_subtle_frame(children)
					self.on_updated_threads()
					self.on_threads_selected(thread, self.selected_frame)
					self._refresh_state()
			run()

		self.on_updated_threads()
		self.refresh_threads()
		self._refresh_state()

	def on_continued_event(self, continued: dap.ContinuedEvent):
		if continued.allThreadsContinued:
			self.all_threads_stopped = False
			for thread in self.threads:
				thread.stopped = False
				thread.stopped_reason = ""

		# @NOTE this thread might be new and not in self.threads so we must update its state explicitly
		thread = self.get_thread(continued.threadId)
		thread.stopped = False
		thread.stopped_reason = ""

		if continued.allThreadsContinued or thread is self.selected_thread:
			self.selected_explicitly = False
			self.selected_thread = None
			self.selected_frame = None
			self.on_threads_selected(None, None)

		self.on_updated_threads()
		self._refresh_state()

	# after a successfull launch/attach, stopped event, thread event we request all threads
	# see https://microsoft.github.io/debug-adapter-protocol/overview
	# updates all the threads from the dap model
	# @NOTE threads_for_id will retain all threads for the entire session even if they are removed
	@core.schedule
	async def refresh_threads(self):
		threads = await self.client.GetThreads()
		self.threads.clear()
		for thread in threads:
			t = self.get_thread(thread.id)
			t.name = thread.name
			self.threads.append(t)

		self.on_updated_threads()

class Thread:
	def __init__(self, session: DebuggerSession, id: int, name: str, stopped: bool):
		self.session = session
		self.id = id
		self.name = name
		self.stopped = stopped
		self.stopped_reason = ""
		self._children = None #type: Optional[core.future]

	def has_children(self) -> bool:
		return self.stopped

	def children(self) -> Awaitable[List[dap.StackFrame]]:
		if not self.stopped:
			raise core.Error('Cannot get children of thread that is not stopped')

		if self._children:
			return self._children
		self._children = core.run(self.session.stack_trace(self.id))
		return self._children

	def clear(self):
		self._children = None
