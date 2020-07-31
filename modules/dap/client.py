'''
	implements the client side of the Debug Adapter protocol

	documentation can be found here
	https://microsoft.github.io/debug-adapter-protocol/specification
	https://microsoft.github.io/debug-adapter-protocol/overview

	a list of server implementers can be found here
	https://microsoft.github.io/debug-adapter-protocol/implementors/adapters/
'''

from ..typecheck import *

import socket
import threading

from .. import core

from .types import *
from .transport import Transport
from .transport import TransportProtocol


class ClientEventsListener (Protocol):
	# events
	def on_initialized_event(self):
		...
	def on_breakpoint_event(self, event: BreakpointEvent):
		...
	def on_module_event(self, event: ModuleEvent):
		...
	def on_loaded_source_event(self, event: LoadedSourceEvent):
		...
	def on_output_event(self, event: OutputEvent):
		...
	def on_terminated_event(self, event: TerminatedEvent):
		...
	def on_stopped_event(self, event: StoppedEvent):
		...
	def on_continued_event(self, event: ContinuedEvent):
		...
	def on_threads_event(self, event: ThreadEvent):
		...
	# reverse requests
	def on_run_in_terminal(self, request: RunInTerminalRequest) -> RunInTerminalResponse:
		...


class Client:
	def __init__(
		self,
		transport: Transport,
		events: ClientEventsListener,
		transport_log: core.Logger,
	) -> None:

		self.events = events
		self.transport_log = transport_log
		transport_log.clear()
		self.transport = TransportProtocol(transport, transport_log)
		self.transport.start(self.transport_message, self.transport_closed)
		self.pending_requests = {} #type: Dict[int, core.future]
		self.seq = 0
		self.is_running = True

	def dispose(self) -> None:
		print('disposing Debugger')
		self.transport.dispose()

	async def StepIn(self, thread: Thread) -> None:
		self._continued(thread.id, False)
		await self.send_request_asyc('stepIn', {
			'threadId': thread.id
		})

	async def StepOut(self, thread: Thread) -> None:
		self._continued(thread.id, False)
		await self.send_request_asyc('stepOut', {
			'threadId': thread.id
		})

	async def StepOver(self, thread: Thread) -> None:
		self._continued(thread.id, False)
		await self.send_request_asyc('next', {
			'threadId': thread.id
		})

	async def Resume(self, thread: Thread) -> None:
		body = await self.send_request_asyc('continue', {
			'threadId': thread.id
		})

		# some adapters aren't giving a response here
		if body:
			self._continued(thread.id, body.get('allThreadsContinued', True))
		else:
			self._continued(thread.id, True)

	async def Pause(self, thread: Thread) -> None:
		await self.send_request_asyc('pause', {
			'threadId': thread.id
		})

	async def Restart(self) -> None:
		await self.send_request_asyc('restart', {
		})

	async def Terminate(self, restart: bool = False) -> None:
		await self.send_request_asyc('terminate', {
			"restart": restart
		})

	async def Disconnect(self, restart: bool = False) -> None:
		await self.send_request_asyc('disconnect', {
			"restart": restart
		})

	async def GetThreads(self) -> List[Thread]:
		response = await self.send_request_asyc('threads', None)
		return array_from_json(Thread.from_json, response['threads'])

	async def GetScopes(self, frame: StackFrame) -> List[Scope]:
		body = await self.send_request_asyc('scopes', {
			"frameId": frame.id
		})
		return array_from_json(Scope.from_json, body['scopes'])

	async def StackTrace(self, threadId: int) -> List[StackFrame]:
		body = await self.send_request_asyc('stackTrace', {
			"threadId": threadId,
		})
		return array_from_json(StackFrame.from_json, body['stackFrames'])

	async def GetSource(self, source: Source) -> str:
		body = await self.send_request_asyc('source', {
			'source': {
				'path': source.path,
				'sourceReference': source.sourceReference
			},
			'sourceReference': source.sourceReference
		})
		return body['content']

	async def Evaluate(self, expression: str, frame: Optional[StackFrame], context: Optional[str]) -> Optional[EvaluateResponse]:
		frameId = None #type: Optional[int]
		if frame:
			frameId = frame.id

		response = await self.send_request_asyc("evaluate", {
			"expression": expression,
			"context": context,
			"frameId": frameId,
		})

		# the spec doesn't say this is optional? But it seems that some implementations throw errors instead of marking things as not verified?
		if response['result'] is None:
			return None
		# variablesReference doesn't appear to be optional in the spec... but some adapters treat it as such
		return EvaluateResponse(response["result"], response.get("variablesReference", 0))

	async def Completions(self, text: str, column: int, frame: Optional[StackFrame]) -> List[CompletionItem]:
		frameId = None
		if frame:
			frameId = frame.id

		response = await self.send_request_asyc("completions", {
			"frameId": frameId,
			"text": text,
			"column": column,
		})
		return array_from_json(CompletionItem.from_json, response['targets'])

	async def setVariable(self, variable: Variable, value: str) -> Variable:
		response = await self.send_request_asyc("setVariable", {
			"variablesReference": variable.containerVariablesReference,
			"name": variable.name,
			"value": value,
		})

		variable.value = response['value']
		variable.variablesReference = response.get('variablesReference', 0)
		return variable

	async def Initialize(self) -> Capabilities:
		response = await self.send_request_asyc("initialize", {
			"clientID": "sublime",
			"clientName": "Sublime Text",
			"adapterID": "python",
			"pathFormat": "path",
			"linesStartAt1": True,
			"columnsStartAt1": True,
			"supportsVariableType": True,
			"supportsVariablePaging": False,
			"supportsRunInTerminalRequest": True,
			"locale": "en-us"}
		)
		return Capabilities.from_json(response)

	async def Launch(self, config: dict, restart: Optional[Any], no_debug: bool) -> None:
		if restart or no_debug:
			config = config.copy()
		if restart:
			config["__restart"] = restart
		if no_debug:
			config["noDebug"] = True

		await self.send_request_asyc('launch', config)
		# the spec says to grab the baseline threads here?
		self.is_running = True

	async def Attach(self, config: dict, restart: Optional[Any], no_debug: bool) -> None:
		if restart or no_debug:
			config = config.copy()
		if restart:
			config["__restart"] = restart
		if no_debug:
			config["noDebug"] = True

		await self.send_request_asyc('attach', config)
		# the spec says to grab the baseline threads here?
		self.is_running = True

	async def SetExceptionBreakpoints(self, filters: List[str]) -> None:
		await self.send_request_asyc('setExceptionBreakpoints', {
			'filters': filters
		})

	async def SetFunctionBreakpoints(self, breakpoints: List[FunctionBreakpoint]) -> List[BreakpointResult]:
		response = await self.send_request_asyc('setFunctionBreakpoints', {
			"breakpoints": json_from_array(FunctionBreakpoint.into_json, breakpoints)
		})
		return array_from_json(BreakpointResult.from_json, response['breakpoints'])

	async def DataBreakpointInfoRequest(self, variable: Variable) -> DataBreakpointInfoResponse:
		response = await self.send_request_asyc('dataBreakpointInfo', {
			"variablesReference": variable.containerVariablesReference,
			"name": variable.name,
		})
		return DataBreakpointInfoResponse.from_json(response)

	async def SetDataBreakpointsRequest(self, breakpoints: List[DataBreakpoint]) -> List[BreakpointResult]:
		response = await self.send_request_asyc('setDataBreakpoints', {
			"breakpoints": json_from_array(DataBreakpoint.into_json, breakpoints)
		})
		return array_from_json(BreakpointResult.from_json, response['breakpoints'])

	async def SetBreakpointsFile(self, file: str, breakpoints: List[SourceBreakpoint]) -> List[BreakpointResult]:
		response = await self.send_request_asyc('setBreakpoints', {
			"source": {
				"path": file
			},
			"breakpoints": json_from_array(SourceBreakpoint.into_json, breakpoints)
		})
		return array_from_json(BreakpointResult.from_json, response['breakpoints'])

	async def ConfigurationDone(self) -> None:
		await self.send_request_asyc('configurationDone', None)

	async def GetVariables(self, variablesReference: int) -> List[Variable]:
		response = await self.send_request_asyc('variables', {
			"variablesReference": variablesReference
		})
		def from_json(v):
			return Variable.from_json(variablesReference, v)

		return array_from_json(from_json, response['variables'])

	def _on_continued(self, body: dict) -> None:
		threadId = body['threadId']
		self._continued(threadId, body.get('allThreadsContinued', True))

	def _continued(self, threadId: int, allThreadsContinued: bool) -> None:
		event = ContinuedEvent(threadId, allThreadsContinued)
		self.events.on_continued_event(event)

	def _on_stopped(self, body: dict) -> None:
		# only ask for threads if there was a reason for the stoppage
		threadId = body.get('threadId', None)
		allThreadsStopped = body.get('allThreadsStopped', False)

		# stopped events are required to have a reason but some adapters treat it as optional...
		description = body.get('description')
		text = body.get('text')
		reason = body.get('reason')

		if description and text:
			stopped_text = "Stopped: {}: {}".format(description, text)
		elif text or description or reason:
			stopped_text = "Stopped: {}".format(text or description or reason)
		else:
			stopped_text = "Stopped"

		event = StoppedEvent(threadId, allThreadsStopped, stopped_text)
		self.events.on_stopped_event(event)

	def _on_terminated(self, body: dict) -> None:
		self.is_running = False
		self.events.on_terminated_event(TerminatedEvent.from_json(body))

	def transport_closed(self) -> None:
		if self.is_running:
			core.log_error('Debug Adapter process was terminated prematurely')
			self._on_terminated({})

	def transport_message(self, message: dict) -> None:
		self.recieved_msg(message)

	def send_request_asyc(self, command: str, args: Optional[dict]) -> Awaitable[dict]:
		future = core.create_future()
		self.seq += 1
		request = {
			"seq": self.seq,
			"type": "request",
			"command": command,
			"arguments": args
		}

		self.pending_requests[self.seq] = future

		self.log_transport(True, request)
		self.transport.send(request)

		return future

	def send_response(self, request: dict, body: dict, error: Optional[str] = None) -> None:
		self.seq += 1

		if error:
			success = False
		else:
			success = True

		data = {
			"type": "response",
			"seq": self.seq,
			"request_seq": request['seq'],
			"command": request['command'],
			"success": success,
			"message": error,
		}

		self.log_transport(True, data)
		self.transport.send(data)

	def log_transport(self, out: bool, data: dict):
		type = data.get('type')

		def sigal(success: bool):
			if success:
				if out:
					return '⟸'
				else:
					return '⟹'
			else:
				if out:
					return '⟽'
				else:
					return '⟾'

		if type == 'response':
			id = data.get('request_seq')
			command = data.get('command')
			body = data.get('body', data.get('message'))
			self.transport_log.info(f'{sigal(data.get("success", False))} response/{command}({id}) :: {body}')
			return

		if type == 'request':
			id = data.get('seq')
			command = data.get('command')
			body = data.get('arguments')
			self.transport_log.info(f'{sigal(True)} request/{command}({id}) :: {body}')
			return

		if type == 'event':
			command = data.get('event')
			body = data.get('body')
			self.transport_log.info(f'{sigal(True)} event/{command} :: {body}')
			return

		self.transport_log.info(f'{sigal(True)} {type}/unknown :: {data}')

	def handle_reverse_request_run_in_terminal(self, request: dict):
		command = RunInTerminalRequest.from_json(request['arguments'])
		try:
			response = self.events.on_run_in_terminal(command)
			self.send_response(request, response.into_json())
		except core.Error as e:
			self.send_response(request, {}, error=str(e))

	def handle_reverse_request(self, request: dict):
		command = request['command']
		if command == 'runInTerminal':
			self.handle_reverse_request_run_in_terminal(request)
			return

		self.send_response(request, {}, error="request not supported by client: {}".format(command))

	def recieved_msg(self, data: dict) -> None:
		t = data['type']
		self.log_transport(False, data)

		if t == 'response':
			try:
				future = self.pending_requests.pop(data['request_seq'])
			except KeyError:
				# the python adapter seems to send multiple initialized responses?
				core.log_info("ignoring request request_seq not found")
				return

			success = data['success']
			if not success:
				body = data.get('body')
				if body:
					error = body.get('error', '')
					future.set_exception(Error.from_json(error))
					return

				future.set_exception(Error(True, data.get('message', 'no error message')))
				return
			else:
				body = data.get('body', {})
				future.set_result(body)
			return

		if t == 'request':
			self.handle_reverse_request(data)

		if t == 'event':
			event_body = data.get('body', {})
			event = data['event']

			if event == 'initialized':
				core.call_soon(self.events.on_initialized_event)
			elif event == 'output':
				core.call_soon(self.events.on_output_event, OutputEvent.from_json(event_body))
			elif event == 'continued':
				core.call_soon(self._on_continued, event_body)
			elif event == 'stopped':
				core.call_soon(self._on_stopped, event_body)
			elif event == 'terminated':
				core.call_soon(self._on_terminated, event_body)
			elif event == 'thread':
				core.call_soon(self.events.on_threads_event, ThreadEvent.from_json(event_body))
			elif event == 'breakpoint':
				core.call_soon(self.events.on_breakpoint_event, BreakpointEvent.from_json(event_body))
			elif event == 'module':
				core.call_soon(self.events.on_module_event, ModuleEvent(event_body))
			elif event == 'loadedSource':
				core.call_soon(self.events.on_loaded_source_event, LoadedSourceEvent(event_body))
			else:
				# TODO should be logged that we aren't handling this event
				...
