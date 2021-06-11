from __future__ import annotations
from ..typecheck import *

from enum import IntEnum

from ..import core

from ..breakpoints import (
	Breakpoints,
	SourceBreakpoint,
)

from ..watch import Watch

from . import types as dap

from .variable import (
	Variable,
	SourceLocation,
	ScopeReference,
)
from .configuration import (
	AdapterConfiguration,
	ConfigurationExpanded,
	TaskExpanded
)

from .types import array_from_json, json_from_array
from .transport import TransportProtocol, TransportProtocolListener

class SessionListener (Protocol):
	async def on_session_task_request(self, session: Session, task: TaskExpanded): ...
	async def on_session_terminal_request(self, session: Session, request: dap.RunInTerminalRequest) -> dap.RunInTerminalResponse: ...

	def on_session_state_changed(self, session: Session, state: Session.State): ...
	def on_session_selected_frame(self, session: Session, frame: Optional[dap.StackFrame]): ...
	def on_session_output_event(self, session: Session, event: dap.OutputEvent): ...

	def on_session_updated_modules(self, session: Session): ...
	def on_session_updated_sources(self, session: Session): ...
	def on_session_updated_variables(self, session: Session): ...
	def on_session_updated_threads(self, session: Session): ...


class Session(TransportProtocolListener, core.Logger):

	class State (IntEnum):
		STARTING = 3
		STOPPED = 0
		STOPPING = 4

		# puased/running is based on selected thread
		PAUSED = 1
		RUNNING = 2

	stopped_reason_build_failed=0
	stopped_reason_launch_error=1
	stopped_reason_dispose=2
	stopped_reason_cancel=3
	stopped_reason_terminated_event=4
	stopped_reason_manual=5


	def __init__(self, 
		adapter_configuration: AdapterConfiguration, 
		configuration: ConfigurationExpanded, 
		restart: Any|None, 
		no_debug: bool, 
		breakpoints: Breakpoints, 
		watch: Watch, 
		listener: SessionListener, 
		transport_log: core.Logger, 
		parent: Session|None = None
		) -> None:

		self.adapter_configuration = adapter_configuration
		self.configuration = configuration
		self.restart = restart
		self.no_debug = no_debug

		self.listener = listener
		self.children: list[Session] = []
		self.parent = parent
		
		if parent:
			parent.children.append(self)

		self.transport_log = transport_log
		self.state_changed = core.Event[int]()

		self.breakpoints = breakpoints
		self.breakpoints_for_id: dict[int, SourceBreakpoint] = {}
		self.breakpoints.data.on_send.add(self.on_send_data_breakpoints)
		self.breakpoints.function.on_send.add(self.on_send_function_breakpoints)
		self.breakpoints.filters.on_send.add(self.on_send_filters)
		self.breakpoints.source.on_send.add(self.on_send_source_breakpoint)

		self.watch = watch
		self.watch.on_added.add(lambda expr: self.watch.evaluate_expression(self, self.selected_frame, expr))

		self._transport: Optional[TransportProtocol] = None

		self.launching_async: Optional[core.Future] = None
		self.capabilities: Optional[dap.Capabilities] = None
		self.stop_requested = False
		self.launch_request = True

		self._state = Session.State.STARTING
		self._status = 'Starting'

		self.disposeables: list[Any] = []

		self.complete: core.Future[None] = core.Future()

		self.threads_for_id: dict[int, Thread] = {}
		self.all_threads_stopped = False
		self.selected_explicitly = False
		self.selected_thread = None
		self.selected_frame = None

		self.threads: list[Thread] = []
		self.variables: list[Variable] = []
		self.sources: dict[int|str, dap.Source] = {}
		self.modules: dict[int|str, dap.Module] = {}

	@property
	def name(self) -> str:
		return self.configuration.name

	@property
	def state(self) -> State:
		return self._state

	@state.setter
	def state(self, state: State) -> None:
		if self._state == state:
			return

		self._state = state
		self.listener.on_session_state_changed(self, state)

	@property
	def status(self) -> str|None:
		return self._status

	def _change_status(self, status: str):
		self._status = status
		self.listener.on_session_state_changed(self, self._state)


	async def launch(self) -> None:
		try:
			self.launching_async = core.run(self._launch())
			await self.launching_async
		except core.Error as e:
			self.launching_async = None
			core.log_exception(e)
			self.error('... an error occured, ' + str(e))
			await self.stop_forced(reason=Session.stopped_reason_launch_error)
		except core.CancelledError:
			...

		self.launching_async = None

	async def _launch(self) -> None:
		assert self.state == Session.stopped, 'debugger not in stopped state?'
		self.state = Session.State.STARTING
		self.configuration = await self.adapter_configuration.configuration_resolve(self.configuration)

		if not self.adapter_configuration.installed_version:
			raise core.Error('Debug adapter with type name "{}" is not installed. You can install it by running Debugger: Install Adapters'.format(self.adapter_configuration.type))

		if not await self.run_pre_debug_task():
			self.info('Pre debug command failed, not starting session')
			self.launching_async = None
			await self.stop_forced(reason=Session.stopped_reason_build_failed)
			return

		self._change_status('Starting')
		try:
			transport = await self.adapter_configuration.start(log=self.transport_log, configuration=self.configuration)
		except Exception as e:
			raise core.Error(f'Unable to start the adapter process: {e}')

		self._transport = TransportProtocol(
			transport,
			self,
			self.transport_log
		)

		self.capabilities = dap.Capabilities.from_json(
			await self.request('initialize', {
				'clientID': 'sublime',
				'clientName': 'Sublime Text',
				'adapterID': self.configuration.type,
				'pathFormat': 'path',
				'linesStartAt1': True,
				'columnsStartAt1': True,
				'supportsVariableType': True,
				'supportsVariablePaging': False,
				'supportsRunInTerminalRequest': True,
				'locale': 'en-us'
			})
		)

		# remove/add any exception breakpoint filters
		self.breakpoints.filters.update(self.capabilities.exceptionBreakpointFilters or [])

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
		self._change_status('Running')
		self.state = Session.State.RUNNING

	async def request(self, command: str, arguments: Any) -> Any:
		if not self._transport:
			raise core.Error('debugger not running')

		return await self._transport.send_request_asyc(command, arguments)

	async def wait(self) -> None:
		await self.complete

	async def run_pre_debug_task(self) -> bool:
		pre_debug_command = self.configuration.pre_debug_task
		if pre_debug_command:
			self._change_status('Running pre debug command')
			r = await self.run_task('Pre debug command', pre_debug_command)
			return r
		return True

	async def run_post_debug_task(self) -> bool:
		post_debug_command = self.configuration.post_debug_task
		if post_debug_command:
			self._change_status('Running post debug command')
			r = await self.run_task('Post debug command', post_debug_command)
			return r
		return True

	async def run_task(self, name: str, task: TaskExpanded) -> bool:
		try:
			await self.listener.on_session_task_request(self, task)
			return True

		except core.CancelledError:
			self.error(f'{name}: cancelled')
			return False

		except Exception as e:
			core.log_exception()
			self.error(f'{name}: {e}')
			return False

	def _refresh_state(self) -> None:
		try:
			thread = self.command_thread
			if thread.stopped:
				self._change_status('Paused')
				self.state = Session.State.PAUSED
			else:
				self._change_status('Running')
				self.state = Session.State.RUNNING

		except core.Error as e:
			self.state = Session.State.RUNNING

	async def add_breakpoints(self) -> None:
		assert self._transport

		requests = [] #type: list[Awaitable[Any]]

		requests.append(self.set_exception_breakpoint_filters())
		requests.append(self.set_function_breakpoints())

		for file, filebreaks in self.breakpoints.source.breakpoints_per_file().items():
			requests.append(self.set_breakpoints_for_file(file, filebreaks))

		assert self.capabilities
		if self.capabilities.supportsDataBreakpoints:
			requests.append(self.set_data_breakpoints())

		if requests:
			await core.wait(requests)

	async def set_exception_breakpoint_filters(self) -> None:
		if not self._transport:
			return
		filters: list[str] = []
		filterOptions: list[dap.Json] = []

		for f in self.breakpoints.filters:
			if f.enabled:
				filters.append(f.dap.id)
				filterOptions.append({
					'filterId': f.dap.id,
					'condition': f.condition,
				})

		await self.request('setExceptionBreakpoints', {
			'filters': filters,
			'filterOptions': filterOptions
		})

	async def set_function_breakpoints(self) -> None:
		if not self._transport:
			return
		breakpoints = list(filter(lambda b: b.enabled, self.breakpoints.function))

		assert self.capabilities
		if not self.capabilities.supportsFunctionBreakpoints:
			# only show error message if the user tried to set a function breakpoint when they are not supported
			if breakpoints:
				self.error('This debugger does not support function breakpoints')
			return

		dap_breakpoints = list(map(lambda b: b.dap, breakpoints))

		response = await self.request('setFunctionBreakpoints', {
			'breakpoints': json_from_array(dap.FunctionBreakpoint.into_json, dap_breakpoints)
		})
		results = array_from_json(dap.BreakpointResult.from_json, response['breakpoints'])

		for result, b in zip(results, breakpoints):
			self.breakpoints.function.set_result(b, result)

	async def set_data_breakpoints(self) -> None:
		if not self._transport:
			return
		breakpoints = list(filter(lambda b: b.enabled, self.breakpoints.data))
		dap_breakpoints = list(map(lambda b: b.dap, breakpoints))

		response = await self.request('setDataBreakpoints', {
			'breakpoints': json_from_array(dap.DataBreakpoint.into_json, dap_breakpoints)
		})
		results = array_from_json(dap.BreakpointResult.from_json, response['breakpoints'])
		for result, b in zip(results, breakpoints):
			self.breakpoints.data.set_result(b, result)

	async def set_breakpoints_for_file(self, file: str, breakpoints: list[SourceBreakpoint]) -> None:
		if not self._transport:
			return

		assert self.capabilities

		enabled_breakpoints: list[SourceBreakpoint] = []
		dap_breakpoints: list[dap.SourceBreakpoint] = []

		for breakpoint in breakpoints:
			if breakpoint.dap.hitCondition and not self.capabilities.supportsHitConditionalBreakpoints:
				self.error('This debugger does not support hit condition breakpoints')

			if breakpoint.dap.logMessage and not self.capabilities.supportsLogPoints:
				self.error('This debugger does not support log points')

			if breakpoint.dap.condition and not self.capabilities.supportsConditionalBreakpoints:
				self.error('This debugger does not support conditional breakpoints')

			if breakpoint.enabled:
				enabled_breakpoints.append(breakpoint)
				dap_breakpoints.append(breakpoint.dap)

		try:
			response = await self.request('setBreakpoints', {
				'source': { 'path': file },
				'breakpoints': json_from_array(dap.SourceBreakpoint.into_json, dap_breakpoints)
			})
			results = array_from_json(dap.BreakpointResult.from_json, response['breakpoints'])

			if len(results) != len(enabled_breakpoints):
				raise dap.Error(True, 'expected #breakpoints to match results')

			for result, b in zip(results, enabled_breakpoints):
				self.breakpoints.source.set_result(b, result)
				if result.id:
					self.breakpoints_for_id[result.id] = b

		except dap.Error as e:
			for b in enabled_breakpoints:
				self.breakpoints.source.set_result(b, dap.BreakpointResult.failed)

	def on_send_data_breakpoints(self, any: Any):
		core.run(self.set_data_breakpoints())

	def on_send_function_breakpoints(self, any: Any):
		core.run(self.set_function_breakpoints())

	def on_send_filters(self, any: Any):
		core.run(self.set_exception_breakpoint_filters())

	def on_send_source_breakpoint(self, breakpoint: SourceBreakpoint) -> None:
		file = breakpoint.file
		core.run(self.set_breakpoints_for_file(file, self.breakpoints.source.breakpoints_for_file(file)))

	async def stop(self):
		# this seems to be what the spec says to do in the overview
		# https://microsoft.github.io/debug-adapter-protocol/overview

		# haven't started session yet
		if self._transport is None:
			await self.stop_forced(reason=Session.stopped_reason_manual)
			return

		# If the stop is called multiple times then we call disconnect to forefully disconnect
		if self.stop_requested:
			await self.stop_forced(reason=Session.stopped_reason_manual)
			return


		self._change_status('Stop requested')
		self.stop_requested = True

		# first try to terminate if we can
		if self.launch_request and self.capabilities and self.capabilities.supportsTerminateRequest:
			try:
				await self.request('terminate', {
					'restart': False
				})
				return
			except dap.Error as e:
				core.log_exception()


		# we couldn't terminate either not a launch request or the terminate request failed
		# so we foreceully disconnect
		await self.request('disconnect', {
			'restart': False
		})


	def stop_debug_adapter_session(self):
		if self.launching_async:
			self.launching_async.cancel()

		self.breakpoints_for_id = {}

		self.watch.clear_session_data(self)
		self.breakpoints.clear_session_data()

		self.stop_requested = False

		if self._transport:
			self.adapter_configuration.did_stop_debugging(self)
			self._transport.dispose()
			self._transport = None


	async def stop_forced(self, reason: int) -> None:
		if self.state == Session.State.STOPPING or self.state == Session.State.STOPPED:
			return

		self.stopped_reason = reason
		self.state = Session.State.STOPPING
		self.stop_debug_adapter_session()

		await self.run_post_debug_task()
		self._change_status('Debug session has ended')

		self.state = Session.State.STOPPED

		print(self.complete)
		if not self.complete.done():
			self.complete.set_result(None)

	def dispose(self) -> None:
		self.stop_debug_adapter_session()
		for disposeable in self.disposeables:
			disposeable.dispose()

		# clean up hierarchy if needed
		for child in self.children:
			child.parent = None

		if self.parent:
			self.parent.children.remove(self)
			self.parent = None

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


	async def pause(self):
		await self.request('pause', {
			'threadId': self.command_thread.id
		})

	async def step_over(self):
		self.on_continued_event(dap.ContinuedEvent(self.command_thread.id, False))

		await self.request('next', {
			'threadId': self.command_thread.id
		})

	async def step_in(self):
		self.on_continued_event(dap.ContinuedEvent(self.command_thread.id, False))

		await self.request('stepIn', {
			'threadId': self.command_thread.id
		})

	async def step_out(self):
		self.on_continued_event(dap.ContinuedEvent(self.command_thread.id, False))

		await self.request('stepOut', {
			'threadId': self.command_thread.id
		})

	async def evaluate(self, expression: str, context: str = 'repl'):
		self.info(expression)

		result = await self.evaluate_expression(expression, context)
		if not result:
			raise dap.Error(True, 'expression did not return a result')
			return

		# variablesReference doesn't appear to be optional in the spec... but some adapters treat it as such
		event = dap.OutputEvent('console', result.result, result.variablesReference)
		self.listener.on_session_output_event(self, event)

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
			raise dap.Error(True, 'expression did not return a result')

		# variablesReference doesn't appear to be optional in the spec... but some adapters treat it as such
		return dap.EvaluateResponse(response['result'], response.get('variablesReference', 0))

	async def stack_trace(self, thread_id: int) -> list[dap.StackFrame]:
		body = await self.request('stackTrace', {
			'threadId': thread_id,
		})
		return dap.array_from_json(dap.StackFrame.from_json, body['stackFrames'])

	async def completions(self, text: str, column: int) -> list[dap.CompletionItem]:
		frameId = None
		if self.selected_frame:
			frameId = self.selected_frame.id

		response = await self.request('completions', {
			'frameId': frameId,
			'text': text,
			'column': column,
		})
		return array_from_json(dap.CompletionItem.from_json, response['targets'])

	async def set_variable(self, variable: dap.Variable, value: str) -> dap.Variable:
		response = await self.request('setVariable', {
			'variablesReference': variable.containerVariablesReference,
			'name': variable.name,
			'value': value,
		})

		variable.value = response['value']
		variable.variablesReference = response.get('variablesReference', 0)
		return variable

	async def data_breakpoint_info(self, variable: dap.Variable) -> dap.DataBreakpointInfoResponse:
		response = await self.request('dataBreakpointInfo', {
			'variablesReference': variable.containerVariablesReference,
			'name': variable.name,
		})
		return dap.DataBreakpointInfoResponse.from_json(response)

	def log_output(self, string: str) -> None:
		output = dap.OutputEvent('debugger.output', string + '\n', 0)
		self.listener.on_session_output_event(self, output)

	def log(self, type: str, value: str) -> None:
		if type == 'process':
			self.transport_log.info(f'⟹ process/stderr :: {value.strip()}')
			return
		if type == 'error':
			output = dap.OutputEvent('debugger.error', value + '\n', 0)
			self.listener.on_session_output_event(self, output)
			return

		output = dap.OutputEvent('debugger.info', value + '\n', 0)
		self.listener.on_session_output_event(self, output)

	def load_frame(self, frame: Optional[dap.StackFrame]):
		self.listener.on_session_selected_frame(self, frame)
		if frame:
			core.run(self.refresh_scopes(frame))
			core.run(self.watch.evaluate(self, self.selected_frame))
		else:
			self.variables.clear()
			self.listener.on_session_updated_variables(self)

	async def refresh_scopes(self, frame: dap.StackFrame):
		body = await self.request('scopes', {
			'frameId': frame.id
		})
		scopes = dap.array_from_json(dap.Scope.from_json, body['scopes'])
		self.variables = [Variable(self, ScopeReference(scope)) for scope in scopes]
		self.listener.on_session_updated_variables(self)

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
		def from_json(v: dap.Json):
			return dap.Variable.from_json(variablesReference, v)

		variables = array_from_json(from_json, response['variables'])

		# vscode seems to remove the names from variables in output events
		if without_names:
			for v in variables:
				v.name = ''

		return [Variable(self, v) for v in variables]

	def on_breakpoint_event(self, event: dap.BreakpointEvent):
		assert event.result.id
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

		self.listener.on_session_updated_modules(self)

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

		self.listener.on_session_updated_sources(self)

	# this is a bit of a weird case. Initialized will happen at some point in time
	# it depends on when the debug adapter chooses it is ready for configuration information
	# when it does happen we can then add all the breakpoints and complete the configuration
	# NOTE: some adapters appear to send the initialized event multiple times
	@core.schedule
	async def on_initialized_event(self):
		try:
			await self.add_breakpoints()
		except core.Error as e:
			self.error('there was an error adding breakpoints {}'.format(e))
		
		assert self.capabilities

		if self.capabilities.supportsConfigurationDoneRequest:
			try:
				await self.request('configurationDone', None)
			except core.Error as e:
				self.error('there was an error in configuration done {}'.format(e))

	def on_output_event(self, event: dap.OutputEvent):
		self.listener.on_session_output_event(self, event)

	@core.schedule
	async def on_terminated_event(self, event: dap.TerminatedEvent):
		await self.stop_forced(reason=Session.stopped_reason_terminated_event)
		# TODO: This needs to be handled inside debugger_sessions
		# restarting needs to be handled by creating a new session
		# if event.restart:
		# 	await self.launch(self.adapter_configuration, self.configuration, event.restart)

	async def on_reverse_request(self, command: str, arguments: dap.Json):
		if command == 'runInTerminal':
			response = await self.on_run_in_terminal(dap.RunInTerminalRequest.from_json(arguments))
			return response.into_json()

		assert self.adapter_configuration
		response = await self.adapter_configuration.on_custom_request(self, command, arguments)

		if response is None:
			raise core.Error(f'reverse request not implemented {command}')

		return response

	async def on_run_in_terminal(self, request: dap.RunInTerminalRequest) -> dap.RunInTerminalResponse:
		try:
			return await self.listener.on_session_terminal_request(self, request)
		except core.Error as e:
			self.error(str(e))
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

	def set_selected(self, thread: Thread, frame: Optional[dap.StackFrame]):
		self.select(thread, frame, explicitly=True)
		self.listener.on_session_updated_threads(self)
		self._refresh_state()

	# after a successfull launch/attach, stopped event, thread event we request all threads
	# see https://microsoft.github.io/debug-adapter-protocol/overview
	# updates all the threads from the dap model
	# @NOTE threads_for_id will retain all threads for the entire session even if they are removed
	@core.schedule
	async def refresh_threads(self):
		response = await self.request('threads', None)
		threads = array_from_json(dap.Thread.from_json, response['threads'])

		self.threads.clear()
		for thread in threads:
			t = self.get_thread(thread.id)
			t.name = thread.name
			self.threads.append(t)

		self.listener.on_session_updated_threads(self)

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
			self.select(thread, None, explicitly=False)

			@core.schedule
			async def run(thread: Thread = thread):
				children = await thread.children()
				if children and not self.selected_frame and not self.selected_explicitly and self.selected_thread is thread:
					def first_non_subtle_frame(frames: list[dap.StackFrame]):
						for frame in frames:
							if frame.presentation != dap.StackFrame.subtle:
								return frame
						return frames[0]

					frame = first_non_subtle_frame(children)
					self.select(thread, frame, explicitly=False)

					self.listener.on_session_updated_threads(self)
					self._refresh_state()
			run()

		self.listener.on_session_updated_threads(self)
		self.refresh_threads()
		self._refresh_state()

	def on_continued_event(self, continued: dap.ContinuedEvent):
		if continued.allThreadsContinued:
			self.all_threads_stopped = False
			for thread in self.threads:
				thread.stopped = False
				thread.stopped_reason = ''

		# @NOTE this thread might be new and not in self.threads so we must update its state explicitly
		thread = self.get_thread(continued.threadId)
		thread.stopped = False
		thread.stopped_reason = ''

		if continued.allThreadsContinued or thread is self.selected_thread:
			self.select(None, None, explicitly=False)

		self.listener.on_session_updated_threads(self)
		self._refresh_state()

	def select(self, thread: Optional[Thread], frame: Optional[dap.StackFrame], explicitly: bool):
		self.selected_explicitly = explicitly
		self.selected_thread = thread
		self.selected_frame = frame
		self.load_frame(frame)

	def on_event(self, event: str, body: dap.Json):
		if event == 'initialized':
			self.on_initialized_event()
		elif event == 'output':
			self.on_output_event(dap.OutputEvent.from_json(body))
		elif event == 'continued':
			self.on_continued_event(dap.ContinuedEvent.from_json(body))
		elif event == 'stopped':
			self.on_stopped_event(dap.StoppedEvent.from_json(body))
		elif event == 'terminated':
			self.on_terminated_event(dap.TerminatedEvent.from_json(body))
		elif event == 'thread':
			self.on_threads_event(dap.ThreadEvent.from_json(body))
		elif event == 'breakpoint':
			self.on_breakpoint_event(dap.BreakpointEvent.from_json(body))
		elif event == 'module':
			self.on_module_event(dap.ModuleEvent.from_json(body))
		elif event == 'loadedSource':
			self.on_loaded_source_event(dap.LoadedSourceEvent.from_json(body))
		else:
			raise dap.Error(True, 'event ignored not implemented')


class Thread:
	def __init__(self, session: Session, id: int, name: str, stopped: bool):
		self.session = session
		self.id = id
		self.name = name
		self.stopped = stopped
		self.stopped_reason = ''
		self._children: Optional[core.Future[list[dap.StackFrame]]] = None

	def has_children(self) -> bool:
		return self.stopped

	def children(self) -> Awaitable[list[dap.StackFrame]]:
		if not self.stopped:
			raise core.Error('Cannot get children of thread that is not stopped')

		if self._children:
			return self._children
		self._children = core.run(self.session.stack_trace(self.id))
		return self._children

	def clear(self):
		self._children = None
