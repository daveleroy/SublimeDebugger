from __future__ import annotations
from ..typecheck import *

from ..import core, dap

from ..dap.transport import (
	Process,
	StdioTransport
)
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

from .variables import Variables
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
		threads: Threads,
		sources: Sources,
		modules: Modules,
		watch: Watch,
		variables: Variables,
		terminals: Terminals,
		on_state_changed: Callable[[int], None],
		on_output: Callable[[dap.OutputEvent], None],
		on_selected_frame: Callable[[Optional[dap.StackFrame]], None],
	) -> None:

		self.state_changed = core.Event() #type: core.Event[int]
		self.modules = modules
		self.sources = sources
		self.variables = variables
		self.callstack = threads
		self.callstack.on_selected_frame.add(lambda frame: self.load_frame(frame))
		self.callstack.on_selected_thread.add(lambda thread: self._refresh_state())
		self.terminals = terminals
		self.terminals_updated = core.Event() #type: core.Event[None]

		self.breakpoints = breakpoints
		self.breakpoints_for_id = {} #type: Dict[int, SourceBreakpoint]
		self.breakpoints.data.on_send.add(self.on_send_data_breakpoints)
		self.breakpoints.function.on_send.add(self.on_send_function_breakpoints)
		self.breakpoints.filters.on_send.add(self.on_send_filters)
		self.breakpoints.source.on_send.add(self.on_send_source_breakpoint)

		self.watch = watch
		self.watch.on_added.add(lambda expr: self.watch.evaluate_expression(self, self.callstack.selected_frame, expr))
		self.on_state_changed = on_state_changed
		self.on_output = on_output
		self.on_selected_frame = on_selected_frame

		self.adapter = None #type: Optional[dap.Client]
		self.process = None #type: Optional[Process]
		self.launching_async = None #type: Optional[core.future]
		self.stop_requested = False
		self.launch_request = True
		self._state = DebuggerSession.stopped

		self.disposeables = [] #type: List[Any]

	def dispose_terminals(self):
		self.terminals.clear_session_data(self)

	def dispose(self) -> None:
		self.clear_session()
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

	async def launch(self, adapter_configuration: Adapter, configuration: ConfigurationExpanded, restart: Optional[Any] = None, no_debug: bool = False) -> None:
		if self.launching_async:
			self.launching_async.cancel()

		self.dispose_terminals()
		try:
			self.launching_async = core.run(self._launch(adapter_configuration, configuration, restart, no_debug))
			await self.launching_async
		except core.Error as e:
			self.launching_async = None
			core.log_exception(e)
			self.error("... an error occured, " + str(e))
			await self.stop_forced(reason=DebuggerSession.stopped_reason_launch_error)
			raise e
		except core.CancelledError:
			self.launching_async = None
			self.info("... canceled")
			await self.stop_forced(reason=DebuggerSession.stopped_reason_cancel)

		self.launching_async = None


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
			self.terminals.add(self, terminal)
			await terminal.wait()
			self.info('... finished')
			return True
		except Exception as e:
			self.error(f'... failed: {e}')
			return False

	async def _launch(self, adapter_configuration: Adapter, configuration: ConfigurationExpanded, restart: Optional[Any], no_debug: bool) -> None:
		if self.state != DebuggerSession.stopped:
			await self.stop()
			return

		assert self.state == DebuggerSession.stopped, "debugger not in stopped state?"
		self.state = DebuggerSession.starting
		self.adapter_configuration = adapter_configuration
		self.configuration = configuration

		if not adapter_configuration.installed_version:
			install = 'Debug adapter with type name "{}" is not installed.\n Would you like to install it?'.format(adapter_configuration.type)
			if sublime.ok_cancel_dialog(install, 'Install'):
				await adapter_configuration.install(self)

		if not adapter_configuration.installed_version:
			raise core.Error('Debug adapter with type name "{}" is not installed. You can install it by running Debugger: Install Adapters'.format(adapter_configuration.type))

		if not await self.run_pre_debug_task():
			await self.stop_forced(reason=DebuggerSession.stopped_reason_build_failed)
			return

		# dont monitor stdout the StdioTransport uses it
		transport = await adapter_configuration.start(log=self)

		adapter = dap.Client(
			transport,
			self
		)
		self.adapter = adapter

		self.info("starting debugger... ")

		# this is a bit of a weird case. Initialized will happen at some point in time
		# it depends on when the debug adapter chooses it is ready for configuration information
		# when it does happen we can then add all the breakpoints and complete the configuration
		async def Initialized() -> None:
			try:
				await adapter.Initialized()
			except Exception as e:
				self.error("there was waiting for initialized from debugger {}".format(e))

			try:
				await self.add_breakpoints()
			except Exception as e:
				self.error("there was an error adding breakpoints {}".format(e))

			try:
				if self.capabilities.supportsConfigurationDoneRequest:
					await adapter.ConfigurationDone()
			except Exception as e:
				self.error("there was an error in configuration done {}".format(e))
		core.run(Initialized())

		self.capabilities = await adapter.Initialize()
		# remove/add any exception breakpoint filters
		self.breakpoints.filters.update(self.capabilities.exceptionBreakpointFilters or [])

		if configuration.request == 'launch':
			self.launch_request = True
			await adapter.Launch(configuration.all, restart, no_debug)
		elif configuration.request == 'attach':
			self.launch_request = False
			await adapter.Attach(configuration.all, restart, no_debug)
		else:
			raise core.Error('expected configuration to have request of either "launch" or "attach" found {}'.format(configuration.request))

		# get the baseline threads after launch/attach
		# according to https://microsoft.github.io/debug-adapter-protocol/overview
		self.refresh_threads()

		# At this point we are running?
		self.state = DebuggerSession.running

	def _refresh_state(self) -> None:
		thread = self.callstack.command_thread()
		if thread and thread.stopped:
			self.state = DebuggerSession.paused
		else:
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
			if self.capabilities.supportsTerminateRequest:
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

		self.variables.clear_session_data()
		self.modules.clear_session_date(self)
		self.sources.clear_session_date(self)
		self.watch.clear_session_data(self)
		self.breakpoints.clear_session_data()
		self.callstack.clear_session_data()

		if self.adapter:
			self.adapter.dispose()
			self.adapter = None
		if self.process:
			self.process.dispose()
			self.process = None
			
	async def stop_forced(self, reason) -> None:
		self.stopped_reason = reason
		self.state = DebuggerSession.stopping
		self.clear_session()
		await self.run_post_debug_task()
		self.state = DebuggerSession.stopped

	@property
	def client(self) -> dap.Client:
		if not self.adapter:
			raise core.Error('debugger not running')
		return self.adapter

	@property
	def command_thread(self) -> dap.Thread:
		return self.callstack.command_thread()

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
		response = await self.client.Evaluate(command, self.callstack.selected_frame, "repl")
		event = dap.OutputEvent("console", response.result, response.variablesReference)
		self.on_output(event)

	def log_output(self, string: str) -> None:
		output = dap.OutputEvent("debugger.output", string + '\n', 0)
		self.on_output(output)

	def info(self, string: str) -> None:
		output = dap.OutputEvent("debugger.info", string + '\n', 0)
		self.on_output(output)

	def error(self, string: str) -> None:
		output = dap.OutputEvent("debugger.error", string + '\n', 0)
		self.on_output(output)

	# after a successfull launch/attach, stopped event, thread event we request all threads
	# see https://microsoft.github.io/debug-adapter-protocol/overview
	def refresh_threads(self) -> None:
		async def refresh_threads():
			threads = await self.client.GetThreads()
			self.callstack.update(self.client, threads)
		core.run(refresh_threads())

	def load_frame(self, frame: Optional[dap.StackFrame]):
		self.on_selected_frame(frame)
		if frame:
			core.run(self.get_scopes(frame))
			core.run(self.watch.evaluate(self, self.callstack.selected_frame))

	async def get_scopes(self, frame: dap.StackFrame):
		scopes = await self.client.GetScopes(frame)
		self.variables.update(self, scopes)

	def on_breakpoint_event(self, event: dap.BreakpointEvent):
		b = self.breakpoints_for_id.get(event.result.id)
		if b:
			self.breakpoints.source.set_result(b, event.result)

	def on_module_event(self, event: dap.ModuleEvent):
		self.modules.on_module_event(self, event)

	def on_loaded_source_event(self, event: dap.LoadedSourceEvent):
		self.sources.on_loaded_source_event(self, event)

	def on_output_event(self, event: dap.OutputEvent):
		self.on_output(event)

	def on_threads_event(self, event: dap.ThreadEvent) -> None:
		self.refresh_threads()

	def on_stopped_event(self, event: dap.StoppedEvent):
		self.callstack.on_stopped_event(self.client, event)
		self.refresh_threads()
		self._refresh_state()

	def on_continued_event(self, event: dap.ContinuedEvent):
		self.callstack.on_continued_event(self.client, event)
		self._refresh_state()

	def on_terminated_event(self, event: dap.TerminatedEvent):
		async def on_terminated_async():
			await self.stop_forced(reason=DebuggerSession.stopped_reason_terminated_event)
			if event.restart:
				await self.launch(self.adapter_configuration, self.configuration, event.restart)

		core.run(on_terminated_async())

	def on_run_in_terminal(self, request: dap.RunInTerminalRequest) -> dap.RunInTerminalResponse:
		try:
			return self.terminals.on_terminal_request(self, request)
		except core.Error as e:
			self.error(str(e))
			raise e


class Sources:
	def __init__(self):
		self.sources = [] #type: List[dap.Source]
		self.on_updated = core.Event() #type: core.Event[None]

	def on_loaded_source_event(self, session: DebuggerSession, event: dap.LoadedSourceEvent) -> None:
		if event.reason == dap.LoadedSourceEvent.new:
			self.sources.append(event.source)
			self.on_updated()
			return
		if event.reason == dap.LoadedSourceEvent.removed:
			# FIXME: NOT IMPLEMENTED
			return
		if event.reason == dap.LoadedSourceEvent.changed:
			# FIXME: NOT IMPLEMENTED
			return

	def clear_session_date(self, session: DebuggerSession) -> None:
		self.sources.clear()
		self.on_updated()


class Modules:
	def __init__(self):
		self.expanded = {} #type: Dict[int, bool]
		self.modules = [] #type: List[dap.Module]
		self.on_updated = core.Event() #type: core.Event[None]

	def toggle_expanded(self, id) -> None:
		expanded = self.expanded.get(id, False)
		self.expanded[id] = not expanded
		self.on_updated()

	def on_module_event(self, session: DebuggerSession, event: dap.ModuleEvent) -> None:
		if event.reason == dap.ModuleEvent.new:
			self.modules.append(event.module)
			self.on_updated()
			return
		if event.reason == dap.ModuleEvent.removed:
			# FIXME: NOT IMPLEMENTED
			return
		if event.reason == dap.ModuleEvent.changed:
			# FIXME: NOT IMPLEMENTED
			return

	def clear_session_date(self, session: DebuggerSession) -> None:
		self.expanded.clear()
		self.modules.clear()
		self.on_updated()


class Thread:
	def __init__(self, id: int, name: str, client: dap.Client, stopped: bool):
		self.id = id
		self.client = client
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
		self._children = core.run(self.client.StackTrace(self.id))
		return self._children

	def clear(self):
		self._children = None


class Threads:
	def __init__(self):
		self.threads = [] #type: List[Thread]
		self.threads_for_id = {}
		self.on_updated = core.Event() #type: core.Event[None]
		self.on_selected_frame = core.Event() #type: core.Event[Optional[dap.StackFrame]]
		self.on_selected_thread = core.Event() #type: core.Event[Optional[Thread]]
		self.all_threads_stopped = False

		self.selected_explicitly = False
		self.selected_thread = None
		self.selected_frame = None

	def command_thread(self) -> Thread:
		if self.selected_thread:
			return self.selected_thread
		if self.threads:
			return self.threads[0]
		raise core.Error("No threads to run command")

	def get_thread(self, client: dap.Client, id: int):
		t = self.threads_for_id.get(id)
		if t:
			return t
		else:
			t = Thread(id, "??", client, self.all_threads_stopped)
			self.threads_for_id[id] = t
			return t

	def set_selected(self, thread: Thread, frame: Optional[dap.StackFrame]):
		self.selected_explicitly = True
		self.selected_thread = thread
		self.selected_frame = frame
		self.on_updated()
		if frame:
			self.on_selected_frame(frame)
		self.on_selected_thread(thread)

	def on_stopped_event(self, client: dap.Client, stopped: dap.StoppedEvent):
		if stopped.allThreadsStopped:
			self.all_threads_stopped = True

			for thread in self.threads:
				thread.clear()
				thread.stopped = True

		# @NOTE this thread might be new and not in self.threads so we must update its state explicitly
		thread = self.get_thread(client, stopped.threadId, )
		thread.clear()
		thread.stopped = True
		thread.stopped_reason = stopped.text

		if self.selected_thread is None:
			self.selected_explicitly = False
			self.selected_thread = thread
			self.selected_frame = None

			self.on_selected_thread(thread)
			self.on_selected_frame(None)

			async def run(thread=thread):
				children = await thread.children()
				if children and not self.selected_frame and not self.selected_explicitly and self.selected_thread is thread:
					def first_non_subtle_frame(frames: List[dap.StackFrame]):
						for frame in frames:
							if frame.presentation != dap.StackFrame.subtle:
								return frame
						return frames[0]

					self.selected_frame = first_non_subtle_frame(children)
					self.on_updated()
					self.on_selected_frame(self.selected_frame)
			core.run(run())

		self.on_updated()

	def on_continued_event(self, client: dap.Client, continued: dap.ContinuedEvent):
		if continued.allThreadsContinued:
			self.all_threads_stopped = False
			for thread in self.threads:
				thread.stopped = False
				thread.stopped_reason = ""

		# @NOTE this thread might be new and not in self.threads so we must update its state explicitly
		thread = self.get_thread(client, continued.threadId)
		thread.stopped = False
		thread.stopped_reason = ""

		if continued.allThreadsContinued or thread is self.selected_thread:
			self.selected_explicitly = False
			self.selected_thread = None
			self.selected_frame = None
			self.on_selected_thread(None)
			self.on_selected_frame(None)

		self.on_updated()

	# updates all the threads from the dap model
	# @NOTE threads_for_id will retain all threads for the entire session even if they are removed
	def update(self, client: dap.Client, threads: List[dap.Thread]):
		self.threads.clear()
		for thread in threads:
			t = self.get_thread(client, thread.id)
			t.name = thread.name
			self.threads.append(t)

		self.on_updated()

	def clear_session_data(self):
		self.threads.clear()
		self.threads_for_id.clear()
		self.selected_explicitly = False
		self.selected_thread = None
		self.selected_frame = None
		self.on_selected_frame(None)
		self.on_updated()
