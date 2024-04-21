from __future__ import annotations
from typing import Any, Awaitable, Callable, cast

from enum import IntEnum

from ..import core
from .import dap

from ..watch import Watch
from .debugger import Console, ConsoleSessionBound, Debugger
from .error import Error

from ..breakpoints import Breakpoints, SourceBreakpoint, Breakpoint
from .variable import Variable

from .adapter import AdapterConfiguration
from .configuration import ConfigurationExpanded, TaskExpanded

from .transport import Transport, TransportConnectionError, TransportListener

class Session(TransportListener, core.Dispose):

	class State (IntEnum):
		STARTING = 3
		STOPPED = 0
		STOPPING = 4

		# puased/running is based on selected thread
		PAUSED = 1
		RUNNING = 2

		def __init__(self, value):
			super().__init__()

			self.status = ''
			self.previous: 'Session.State' = 0 #type: ignore

	on_output: core.Event['Session', dap.OutputEvent]

	on_updated: core.Event['Session']
	on_updated_modules: core.Event['Session']
	on_updated_sources: core.Event['Session']
	on_updated_variables: core.Event['Session']
	on_updated_threads: core.Event['Session']

	on_selected_frame: Callable[['Session', dap.StackFrame|None], None]
	on_finished: Callable[['Session'], None]

	on_task_request: Callable[['Session', TaskExpanded], Awaitable[None]]
	on_terminal_request: Callable[['Session', dap.RunInTerminalRequestArguments], Awaitable[dap.RunInTerminalResponse]]

	def __init__(self,
		adapter_configuration: AdapterConfiguration,
		configuration: ConfigurationExpanded,
		restart: Any|None,
		no_debug: bool,
		breakpoints: Breakpoints,
		watch: Watch,
		console: Console,
		debugger: Debugger,
		parent: Session|None = None
		) -> None:

		self.adapter_configuration = adapter_configuration
		self.configuration = configuration
		self.restart = restart
		self.no_debug = no_debug

		self.children: list[Session] = []
		self.parent = parent
		self.debugger = debugger

		if parent:
			parent.children.append(self)

		self.log = ConsoleSessionBound(self, console)
		self.state_changed = core.Event[int]()

		self.breakpoints = breakpoints
		self.breakpoints_for_id: dict[int, Breakpoint] = {}

		self.dispose_add(
			self.breakpoints.data.on_send.add(self.on_send_data_breakpoints),
			self.breakpoints.function.on_send.add(self.on_send_function_breakpoints),
			self.breakpoints.filters.on_send.add(self.on_send_filters),
			self.breakpoints.source.on_send.add(self.on_send_source_breakpoint),
		)

		self.watch = watch
		self.watch.on_added.add(lambda expr: self.watch.evaluate_expression(self, expr))

		self._transport_started = False
		self._transport: Transport|None = None


		self.launching_async: core.Future|None = None
		self.capabilities = dap.Capabilities()
		self.stop_requested = False
		self.launch_request = True
		self.stepping = False
		self.stepping_hit_stopped_event = False
		self.stopped_unexpectedly = False
		self.terminated_event = None

		self._state = Session.State.STARTING

		self.disposeables: list[Any] = []

		self.threads_for_id: dict[int, Thread] = {}
		self.all_threads_stopped = False
		self.selected_explicitly = False
		self.selected_thread = None
		self.selected_frame = None

		self.threads: list[Thread] = []
		self.variables: list[Variable] = []
		self.sources: dict[int|str, dap.Source] = {}
		self.modules: dict[int|str, dap.Module] = {}

		self.process: dap.ProcessEvent|None = None

	@property
	def name(self) -> str:
		return self.configuration.name or (self.process and self.process.name) or 'Untitled'

	@property
	def state(self) -> State:
		return self._state

	def _change_state(self, state: State) -> None:
		if self._state == state: return

		state.previous = self.state
		self._state = state
		self.on_updated(self)

	def _change_state_status(self, status: str):
		self._state.status = status
		self._state.previous = self._state
		self.on_updated(self)

	async def launch(self) -> None:
		if self.launching_async:
			raise Error('Sessions can only be launched once')

		try:
			self.launching_async = self._launch()
			await self.launching_async

		except core.Error as e:
			core.exception(e)
			self.log.error(str(e), self.configuration.source)
			await self.stop_session()
			raise e

		except core.CancelledError:
			...

	@core.run
	async def _launch(self) -> None:
		assert self.state == Session.State.STOPPED, 'debugger not in stopped state?'
		self._change_state(Session.State.STARTING)
		self.configuration = await self.adapter_configuration.configuration_resolve(self.configuration)

		installed_version = self.adapter_configuration.installed_version
		if not installed_version:
			raise core.Error('Debug adapter with type name "{}" is not installed. You can install it by running Debugger: Install Adapters'.format(self.adapter_configuration.type))

		if not await self.run_pre_debug_task():
			await self.stop_session()
			return

		self._change_state_status('Starting')
		try:
			self.log('transport', f'-- adapter: type={self.adapter_configuration.type} version={installed_version}')
			transport = await self.adapter_configuration.start(log=self.log, configuration=self.configuration)
		except TransportConnectionError as e:
			self.stopped_unexpectedly = True
			raise core.Error(f'Unable to start adapter: {e}')
		except Exception as e:
			raise core.Error(f'Unable to start adapter: {e}')


		self._transport = transport
		await self._transport.start(self, self.configuration, self.log)
		self._transport_started = True

		capabilities: dap.Capabilities = await self.request('initialize', {
			'clientID': 'sublime',
			'clientName': 'Sublime Text',
			'adapterID': self.configuration.type,
			'pathFormat': 'path',
			'linesStartAt1': True,
			'columnsStartAt1': True,
			'supportsVariableType': True,
			'supportsVariablePaging': False,
			'supportsRunInTerminalRequest': True,
			'supportsMemoryReferences': True,
			'locale': 'en-us'
		})
		self.capabilities = capabilities


		# remove/add any exception breakpoint filters
		self.breakpoints.filters.update(capabilities.exceptionBreakpointFilters or [])

		if self.restart:
			self.configuration['__restart'] = self.restart
		if self.no_debug:
			self.configuration['noDebug'] = True

		if self.configuration.request == 'launch':
			self.launch_request = True
			await self.request('launch', self.configuration)
		elif self.configuration.request == 'attach':
			self.launch_request = False
			await self.request('attach', self.configuration)
		else:
			raise core.Error('expected configuration to have request of either "launch" or "attach" found {}'.format(self.configuration.request))

		self.adapter_configuration.did_start_debugging(self)

		# get the baseline threads after launch/attach
		# according to https://microsoft.github.io/debug-adapter-protocol/overview
		self.refresh_threads()

		# At this point we are running?
		self._change_state_status('Running')
		self._change_state(Session.State.RUNNING)

	async def request(self, command: str, arguments: Any) -> Any:
		if not self._transport_started:
			raise core.Error('Debugging not started')

		if not self._transport:
			raise core.Error('Debugging ended')

		return await self._transport.send_request(command, arguments)

	async def run_pre_debug_task(self) -> bool:
		pre_debug_command = self.configuration.pre_debug_task
		if pre_debug_command:
			self._change_state_status('Running pre debug task')
			r = await self.run_task('pre_debug_task', pre_debug_command)
			return r
		return True

	async def run_post_debug_task(self) -> bool:
		post_debug_command = self.configuration.post_debug_task
		if post_debug_command:
			self._change_state_status('Running post debug task')
			r = await self.run_task('post_debug_task', post_debug_command)
			return r
		return True

	async def run_task(self, name: str, task: TaskExpanded) -> bool:
		try:
			await self.on_task_request(self, task)
			return True

		except core.CancelledError:
			self.log('error-no-open', f'{name}: cancelled')
			return False

		except core.Error as e:
			self.log('error-no-open', f'{name}: {e}')
			return False

	def _refresh_state(self) -> None:
		try:
			thread = self.command_thread
			if thread.stopped:
				self._change_state_status('Paused')
				self._change_state(Session.State.PAUSED)
			else:
				self._change_state_status('Running')
				self._change_state(Session.State.RUNNING)

		except core.Error as e:
			self._change_state(Session.State.RUNNING)

	async def add_breakpoints(self) -> None:
		if not self._transport:
			return

		requests: list[Awaitable[Any]] = []

		requests.append(self.set_exception_breakpoint_filters())
		requests.append(self.set_function_breakpoints())

		for file, filebreaks in self.breakpoints.source.breakpoints_per_file().items():
			requests.append(self.set_breakpoints_for_file(file, filebreaks))

		if self.capabilities.supportsDataBreakpoints:
			requests.append(self.set_data_breakpoints())

		await core.gather_results(*requests)


	async def set_exception_breakpoint_filters(self) -> None:
		if not self._transport:
			return
		try:
			filters: list[str] = []
			filterOptions: list[dap.ExceptionFilterOptions] = []

			for f in self.breakpoints.filters:
				if f.enabled:
					filters.append(f.dap.filter)
					filterOptions.append(dap.ExceptionFilterOptions(
						f.dap.filter,
						f.condition,
					))

			await self.request('setExceptionBreakpoints', {
				'filters': filters,
				'filterOptions': filterOptions
			})
		except core.Error as e:
			self.log.error('Error while exception filters: {}'.format(e))

	async def set_function_breakpoints(self) -> None:
		if not self._transport:
			return
		breakpoints = list(filter(lambda b: b.enabled, self.breakpoints.function))

		if not self.capabilities.supportsFunctionBreakpoints:
			# only show error message if the user tried to set a function breakpoint when they are not supported
			if breakpoints:
				self.log.error('This debugger does not support function breakpoints')
			return

		try:
			dap_breakpoints = list(map(lambda b: b.dap, breakpoints))

			response = await self.request('setFunctionBreakpoints', {
				'breakpoints': dap_breakpoints
			})
			results: list[dap.Breakpoint] = response['breakpoints']

			for result, b in zip(results, breakpoints):
				self.breakpoints.function.set_breakpoint_result(b, self, result)
				if result.id is not None:
					self.breakpoints_for_id[result.id] = b

		except core.Error as e:
			self.log.error('Error while adding function breakpoints: {}'.format(e))

	async def set_data_breakpoints(self) -> None:
		if not self._transport:
			return
		breakpoints = list(filter(lambda b: b.enabled, self.breakpoints.data))
		dap_breakpoints = list(map(lambda b: b.dap, breakpoints))

		try:
			response = await self.request('setDataBreakpoints', {
				'breakpoints': dap_breakpoints
			})
			results: list[dap.Breakpoint] = response['breakpoints']
			for result, b in zip(results, breakpoints):
				self.breakpoints.data.set_breakpoint_result(b, self, result)
				if result.id is not None:
					self.breakpoints_for_id[result.id] = b

		except core.Error as e:
			self.log.error('Error while adding data breakpoints: {}'.format(e))

	async def set_breakpoints_for_file(self, file: str, breakpoints: list[SourceBreakpoint]) -> None:
		if not self._transport:
			return

		enabled_breakpoints: list[SourceBreakpoint] = []
		dap_breakpoints: list[dap.SourceBreakpoint] = []

		lines: list[int] = []

		for breakpoint in breakpoints:
			if breakpoint.dap.hitCondition and not self.capabilities.supportsHitConditionalBreakpoints:
				self.log.error('This debugger does not support hit condition breakpoints')

			if breakpoint.dap.logMessage and not self.capabilities.supportsLogPoints:
				self.log.error('This debugger does not support log points')

			if breakpoint.dap.condition and not self.capabilities.supportsConditionalBreakpoints:
				self.log.error('This debugger does not support conditional breakpoints')

			if breakpoint.enabled:
				enabled_breakpoints.append(breakpoint)
				dap_breakpoints.append(breakpoint.dap)
				lines.append(breakpoint.dap.line)

		try:
			response = await self.request('setBreakpoints', {
				'source': { 'path': file },
				'breakpoints': dap_breakpoints,
				'lines': lines, # for backwards compat
			})
			results: list[dap.Breakpoint] = response['breakpoints']

			if len(results) != len(enabled_breakpoints):
				raise Error('expected #breakpoints to match results')

			for result, b in zip(results, enabled_breakpoints):
				self.breakpoints.source.set_breakpoint_result(b, self, result)
				if result.id is not None:
					self.breakpoints_for_id[result.id] = b

		except Error as e:
			self.log.error('Error while adding breakpoints: {}'.format(e))
			for b in enabled_breakpoints:
				self.breakpoints.source.set_breakpoint_result(b, self, dap.Breakpoint(verified=False, message=str(e)))

	def on_send_data_breakpoints(self, any: Any):
		core.run(self.set_data_breakpoints())

	def on_send_function_breakpoints(self, any: Any):
		core.run(self.set_function_breakpoints())

	def on_send_filters(self, any: Any):
		core.run(self.set_exception_breakpoint_filters())

	def on_send_source_breakpoint(self, breakpoint: SourceBreakpoint) -> None:
		core.run(self.set_breakpoints_for_file(breakpoint.file, self.breakpoints.source.breakpoints_for_file(breakpoint.file)))

	async def stop(self):
		# this seems to be what the spec says to do in the overview
		# https://microsoft.github.io/debug-adapter-protocol/overview

		# haven't started session yet
		if self._transport is None:
			await self.stop_session()
			return

		# If the stop is called multiple times then we forcefully stop the session
		if self.stop_requested:
			await self.stop_session()
			return


		self._change_state_status('Stop Requested')
		self.stop_requested = True

		# first try to terminate if we can
		if self.launch_request and self.capabilities.supportsTerminateRequest:
			try:
				await self.request('terminate', {
					'restart': False
				})
				return
			except Error as e:
				core.exception()

		# we couldn't terminate either not a launch request or the terminate request failed
		# so we foreceully disconnect
		await self.request('disconnect', {
			'restart': False,
			'terminateDebuggee': True,
		})

		await self.stop_session()

	async def stop_session(self) -> None:
		if self.state == Session.State.STOPPING or self.state == Session.State.STOPPED:
			return

		if self._transport_started:
			if not self.stop_requested and not self.terminated_event:
				self.stopped_unexpectedly = True

		self._change_state(Session.State.STOPPING)

		self.dispose_adapter_session()

		await self.run_post_debug_task()
		self._change_state_status('Ended')

		self._change_state(Session.State.STOPPED)
		self.on_finished(self)

	def dispose_adapter_session(self):
		if self.launching_async:
			self.launching_async.cancel()

		self.watch.clear_session_data(self)
		self.breakpoints.clear_breakpoint_result(self)

		self.stop_requested = False

		if self._transport:
			self.adapter_configuration.did_stop_debugging(self)
			self._transport.dispose()
			self._transport = None

	def dispose(self) -> None:
		super().dispose()

		self.dispose_adapter_session()

		if self.parent:
			self.parent.children.remove(self)
			self.parent = None

		# clean up hierarchy if needed
		for child in self.children:
			child.parent = None

	async def resume(self):
		body = await self.request('continue', {
			'threadId': self.command_thread.id
		})

		# some adapters aren't giving a response here
		if body:
			allThreadsContinued = body.get('allThreadsContinued', True)
		else:
			allThreadsContinued = True

		self.on_continued_event(dap.ContinuedEvent(self.command_thread.id, allThreadsContinued))

	async def reverse_continue(self):
		if self.capabilities.supportsStepBack:
			body = await self.request('reverseContinue', {
				'threadId': self.command_thread.id
			})

			# some adapters aren't giving a response here
			if body:
				allThreadsContinued = body.get('allThreadsContinued', True)
			else:
				allThreadsContinued = True

			self.on_continued_event(dap.ContinuedEvent(self.command_thread.id, allThreadsContinued))
		else:
			self.log.error('This debugger does not support stepping backwards')

	async def pause(self):
		await self.request('pause', {
			'threadId': self.command_thread.id
		})

	async def step(self, command: str, granularity: str|None = None):
		# this is used to so the ui can better handle stepping
		# Ideally the ui does not switch panels when stepping
		# If the user selects the console and steps the program it ideally doesn't switch to the callstack panel
		self.stepping = True
		self.stepping_hit_stopped_event = False

		thread = self.command_thread

		await self.request(command, {
			'threadId': thread.id,
			'granularity': granularity,
		})
		self.on_continued_event(dap.ContinuedEvent(thread.id, False))

	async def step_over(self, granularity: str|None = None):
		await self.step('next', granularity)

	async def step_in(self, granularity: str|None = None):
		await self.step('stepIn', granularity)

	async def step_out(self, granularity: str|None = None):
		await self.step('stepOut', granularity)

	async def step_back(self, granularity: str|None = None):
		if self.capabilities.supportsStepBack:
			await self.step('stepBack', granularity)
		else:
			self.log.error('This debugger does not support stepping backwards')

	async def exception_info(self, thread_id: int) -> dap.ExceptionInfoResponseBody:
		return await self.request('exceptionInfo', {
			'threadId': thread_id
		})

	async def evaluate(self, expression: str, context: str = 'repl'):
		result = await self.evaluate_expression(expression, context)
		if not result:
			raise Error('expression did not return a result')

		# variablesReference doesn't appear to be optional in the spec... but some adapters treat it as such
		event = dap.OutputEvent(result.result + '\n', 'console', variablesReference=result.variablesReference)
		self.on_output(self, event)

	async def evaluate_expression(self, expression: str, context: str|None) -> dap.EvaluateResponse:
		frameId: int|None = None
		if self.selected_frame:
			frameId = self.selected_frame.id

		response = await self.request('evaluate', {
			'expression': expression,
			'context': context,
			'frameId': frameId,
		})

		# the spec doesn't say this is optional? But it seems that some implementations throw errors instead of marking things as not verified?
		if response['result'] is None:
			raise Error('expression did not return a result')

		return response

	async def disassemble(self, memory_reference: str, instruction_offset: int, instruction_count: int) -> dap.DisassembleResponseBody:
		return await self.request('disassemble', {
			'memoryReference': memory_reference,
			'instructionOffset': instruction_offset,
			'instructionCount': instruction_count,
		})

	async def read_memory(self, memory_reference: str, count: int, offset: int) -> dap.ReadMemoryResponse:
		return await self.request('readMemory', {
			'memoryReference': memory_reference,
			'count': count,
			'offset': offset
		})

	async def stack_trace(self, thread_id: int) -> list[dap.StackFrame]:
		body = await self.request('stackTrace', {
			'threadId': thread_id,
		})
		return body['stackFrames']

	async def completions(self, text: str, column: int) -> list[dap.CompletionItem]:
		frameId = None
		if self.selected_frame:
			frameId = self.selected_frame.id

		response = await self.request('completions', {
			'frameId': frameId,
			'text': text,
			'column': column,
		})
		return response['targets']

	async def set_variable(self, variablesReference: int, name: str, value: str) -> dap.SetVariableResponse:
		return await self.request('setVariable', {
			'variablesReference': variablesReference,
			'name': name,
			'value': value,
		})

	async def data_breakpoint_info(self, variablesReference: int, name: str) -> dap.DataBreakpointInfoResponse:
		response = await self.request('dataBreakpointInfo', {
			'variablesReference': variablesReference,
			'name': name,
		})
		return response

	async def refresh_scopes(self, frame: dap.StackFrame):
		body = await self.request('scopes', {
			'frameId': frame.id
		})
		scopes: list[dap.Scope] = body['scopes']
		self.variables = [Variable.from_scope(self, scope) for scope in scopes]
		self.on_updated_variables(self)

	async def get_source(self, source: dap.Source) -> tuple[str, str|None]:
		body = await self.request('source', {
			'source': {
				'path': source.path,
				'sourceReference': source.sourceReference
			},
			'sourceReference': source.sourceReference
		})
		return body['content'], body.get('mimeType')

	async def get_variables(self, variablesReference: int, without_names: bool = False) -> list[Variable]:
		response = await self.request('variables', {
			'variablesReference': variablesReference
		})

		variables: list[dap.Variable] = response['variables']

		# vscode seems to remove the names from variables in output events
		if without_names:
			for v in variables:
				v.name = ''
				v.value = v.value.split('\n')[0]


		return [Variable.from_variable(self, variablesReference, v) for v in variables]

	def on_breakpoint_event(self, event: dap.BreakpointEvent):
		assert event.breakpoint.id
		if b := self.breakpoints_for_id.get(event.breakpoint.id):
			self.breakpoints.set_breakpoint_result(b, self, event.breakpoint)
		else:
			core.debug(f'Breakpoint for id not found {event.breakpoint.id}')

	def on_module_event(self, event: dap.ModuleEvent):
		if event.reason == 'new':
			self.modules[event.module.id] = event.module

		if event.reason == 'removed':
			try:
				del self.modules[event.module.id]
			except KeyError:
				...
		if event.reason == 'changed':
			self.modules[event.module.id] = event.module

		self.on_updated_modules(self)

	def on_process_event(self, event: dap.ProcessEvent):
		self.process = event
		self.on_updated(self)

	def on_loaded_source_event(self, event: dap.LoadedSourceEvent):
		id = f'{event.source.name}~{event.source.path}~{event.source.sourceReference}'
		if event.reason == 'new':
			self.sources[id] = event.source

		elif event.reason == 'removed':
			try:
				del self.sources[id]
			except KeyError:
				...
		elif event.reason == 'changed':
			self.sources[id] = event.source

		self.on_updated_sources(self)

	# this is a bit of a weird case. Initialized will happen at some point in time
	# it depends on when the debug adapter chooses it is ready for configuration information
	# when it does happen we can then add all the breakpoints and complete the configuration
	# NOTE: some adapters appear to send the initialized event multiple times

	@core.run
	async def on_initialized_event(self):
		await self.add_breakpoints()

		if self.capabilities.supportsConfigurationDoneRequest:
			await self.request('configurationDone', {})

	def on_output_event(self, event: dap.OutputEvent):
		self.on_output(self, event)

	@core.run
	async def on_terminated_event(self, event: dap.TerminatedEvent):
		self.terminated_event = event
		await self.stop()

		# TODO: This needs to be handled inside debugger_sessions
		# restarting needs to be handled by creating a new session
		# if event.restart:
		# 	await self.launch(self.adapter_configuration, self.configuration, event.restart)

	@core.run
	async def on_transport_closed(self):
		await self.stop_session()

	async def on_reverse_request(self, command: str, arguments: core.JSON) -> core.JSON:
		if command == 'runInTerminal':
			response = await self.on_run_in_terminal(cast(dap.RunInTerminalRequestArguments, arguments))
			return cast(core.JSON, response)

		assert self.adapter_configuration
		response = await self.adapter_configuration.on_custom_request(self, command, arguments)

		if response is None:
			raise core.Error(f'reverse request not implemented {command}')

		return cast(core.JSON, response)

	async def on_run_in_terminal(self, request: dap.RunInTerminalRequestArguments) -> dap.RunInTerminalResponse:
		try:
			return await self.on_terminal_request(self, request)
		except core.Error as e:
			self.log.error(str(e))
			raise e

	@property
	def command_thread(self) -> Thread:
		if self.selected_thread:
			return self.selected_thread
		if self.threads:
			return self.threads[0]

		raise core.Error('No threads to run command')

	def get_thread(self, id: int):
		t = self.threads_for_id.get(id)
		if t:
			return t
		else:
			t = Thread(self, id, '??', self.all_threads_stopped)
			self.threads_for_id[id] = t
			return t

	def set_selected(self, thread: Thread, frame: dap.StackFrame|None):
		self.select(thread, frame, explicitly=True)
		self._refresh_state()

	# after a successfull launch/attach, stopped event, thread event we request all threads
	# see https://microsoft.github.io/debug-adapter-protocol/overview
	# updates all the threads from the dap model
	# @NOTE threads_for_id will retain all threads for the entire session even if they are removed
	@core.run
	async def refresh_threads(self):
		# the Java debugger requires an empty object instead of `None`
		# See https://github.com/daveleroy/sublime_debugger/pull/106#issuecomment-793802989
		response = await self.request('threads', {})
		# See https://github.com/daveleroy/sublime_debugger/pull/106#issuecomment-795949070
		threads: list[dap.Thread] = response.get('threads', [])

		self.threads.clear()
		for thread in threads:
			t = self.get_thread(thread.id)
			t.name = thread.name
			self.threads.append(t)

		self.on_updated_threads(self)

	def on_threads_event(self, event: dap.ThreadEvent) -> None:
		self.refresh_threads()

	def on_stopped_event(self, stopped: dap.StoppedEvent):
		self.stepping_hit_stopped_event = True

		if stopped.allThreadsStopped or False:
			self.all_threads_stopped = True

			for thread in self.threads:
				thread.set_stopped(None)


		if stopped.threadId is not None:
			stopped_thread_id = stopped.threadId
		elif self.threads:
			stopped_thread_id = self.threads[0].id
		else:
			stopped_thread_id = None

		if stopped_thread_id is not None:
			thread = self.get_thread(stopped_thread_id)

			# @NOTE this thread might be new and not in self.threads so we must update its state explicitly
			thread.set_stopped(stopped)

			if not self.selected_explicitly:
				self.select(thread, None, explicitly=False)
				self.expand_thread(thread)

		self.on_updated_threads(self)
		self.refresh_threads()
		self._refresh_state()

	@core.run
	async def expand_thread(self, thread: Thread):
		children = await thread.children()
		if children and not self.selected_frame and not self.selected_explicitly and self.selected_thread is thread:
			def first_non_subtle_frame(frames: list[dap.StackFrame]):
				for frame in frames:
					if frame.presentationHint != 'subtle' and frame.source:
						return frame
				return frames[0]

			frame = first_non_subtle_frame(children)
			self.select(thread, frame, explicitly=False)

			self.on_updated_threads(self)
			self._refresh_state()

	def on_continued_event(self, continued: dap.ContinuedEvent):
		# if we hit a stopped event while stepping then the next continue event that is not a stepping event sets stepping to false
		if self.stepping_hit_stopped_event:
			self.stepping = False

		if continued.allThreadsContinued:
			self.all_threads_stopped = False
			for thread in self.threads:
				thread.set_continued(None)

		# @NOTE this thread might be new and not in self.threads so we must update its state explicitly
		thread = self.get_thread(continued.threadId)
		thread.set_continued(continued)

		if continued.allThreadsContinued or thread is self.selected_thread:
			self.select(None, None, explicitly=False)

		self.on_updated_threads(self)
		self._refresh_state()

	def select(self, thread: Thread|None, frame: dap.StackFrame|None, explicitly: bool):
		if frame and not thread:
			raise core.Error('Expected thread')

		self.selected_explicitly = explicitly
		self.selected_thread = thread
		self.selected_frame = frame

		self.on_selected_frame(self, frame)

		if frame:
			core.run(self.refresh_scopes(frame))
			core.run(self.watch.evaluate(self, frame))
		else:
			self.variables.clear()
			self.on_updated_variables(self)

	def on_event(self, event: str, body: Any):
		if not self._transport:
			core.debug('on_event: discarded transport ended')
			return

		if event == 'initialized':
			self.on_initialized_event()
		elif event == 'output':
			self.on_output_event(body)
		elif event == 'continued':
			self.on_continued_event(body)
		elif event == 'stopped':
			self.on_stopped_event(body)
		elif event == 'terminated':
			self.on_terminated_event(body)
		elif event == 'thread':
			self.on_threads_event(body)
		elif event == 'breakpoint':
			self.on_breakpoint_event(body)
		elif event == 'module':
			self.on_module_event(body)
		elif event == 'loadedSource':
			self.on_loaded_source_event(body)
		elif event == 'process':
			self.on_process_event(body)
		else:
			core.run(self.adapter_configuration.on_custom_event(self, event, body))


class Thread:
	def __init__(self, session: Session, id: int, name: str, stopped: bool):
		self.session = session
		self.id = id
		self.name = name
		self.stopped = stopped
		self.stopped_reason = ''
		self.stopped_event: dap.StoppedEvent|None = None
		self._children: core.Future[list[dap.StackFrame]]|None = None

	def has_children(self) -> bool:
		return self.stopped

	def children(self) -> Awaitable[list[dap.StackFrame]]:
		if not self.stopped:
			raise core.Error('Cannot get children of thread that is not stopped')

		if self._children:
			return self._children
		self._children = core.run(self.session.stack_trace(self.id))
		return self._children

	def set_stopped(self, event: dap.StoppedEvent|None):
		self._children = None # children are no longer valid

		self.stopped = True

		if event:
			description = event.description
			text = event.text
			reason = event.reason

			if description and text:
				stopped_text = "Stopped: {}: {}".format(description, text)
			elif text or description or reason:
				stopped_text = "Stopped: {}".format(text or description or reason)
			else:
				stopped_text = "Stopped"

			self.stopped_reason = stopped_text
			self.stopped_event = event

	def set_continued(self, event: dap.ContinuedEvent|None):
		self.stopped = False
		self.stopped_reason = ''
		self.stopped_event = None
