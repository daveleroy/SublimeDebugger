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
import json

from .. import core

from .types import *
from .transport import Transport

class ClientEventsListener (Protocol):
	# events
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
	) -> None:

		self.transport = transport
		self.events = events
		self.transport.start(self.transport_message, self.transport_closed)
		self.pending_requests = {} #type: Dict[int, core.future]
		self.seq = 0
		self.allThreadsStopped = False
		self.is_running = True
		self._on_initialized_future = core.create_future()

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

		threads = []
		for thread in response['threads']:
			thread = Thread(self, thread['id'], thread.get("name"))
			threads.append(thread)

		return threads

	async def GetScopes(self, frame: StackFrame) -> List[Scope]:
		body = await self.send_request_asyc('scopes', {
			"frameId": frame.id
		})
		scopes = []
		for scope_json in body['scopes']:
			scope = Scope.from_json(self, scope_json)
			scopes.append(scope)
		return scopes

	async def GetStackTrace(self, thread: Thread) -> List[StackFrame]:
		body = await self.send_request_asyc('stackTrace', {
			"threadId": thread.id,
		})
		frames = []
		for frame in body['stackFrames']:
			frame = StackFrame.from_json(frame)
			frames.append(frame)
		return frames

	async def StackTrace(self, threadId: int) -> List[StackFrame]:
		body = await self.send_request_asyc('stackTrace', {
			"threadId": threadId,
		})
		frames = []
		for frame in body['stackFrames']:
			frame = StackFrame.from_json(frame)
			frames.append(frame)
		return frames

	async def GetSource(self, source: Source) -> str:
		body = await self.send_request_asyc('source', {
			'source': {
				'path': source.path,
				'sourceReference': source.sourceReference
			},
			'sourceReference': source.sourceReference
		})
		return body['content']

	async def Initialized(self) -> None:
		await self._on_initialized_future

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
		items = [] #type: List[CompletionItem]
		for item in response['targets']:
			items.append(CompletionItem.from_json(item))
		return items

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
		result = await self.send_request_asyc('setFunctionBreakpoints', {
			"breakpoints": json_from_array(FunctionBreakpoint.into_json, breakpoints)
		})
		return array_from_json(BreakpointResult.from_json, result['breakpoints'])

	async def DataBreakpointInfoRequest(self, variable: Variable) -> DataBreakpointInfoResponse:
		result = await self.send_request_asyc('dataBreakpointInfo', {
			"variablesReference": variable.containerVariablesReference,
			"name": variable.name,
		})
		return DataBreakpointInfoResponse.from_json(result)

	async def SetDataBreakpointsRequest(self, breakpoints: List[DataBreakpoint]) -> List[BreakpointResult]:
		result = await self.send_request_asyc('setDataBreakpoints', {
			"breakpoints": json_from_array(DataBreakpoint.into_json, breakpoints)
		})
		return array_from_json(BreakpointResult.from_json, result['breakpoints'])

	async def SetBreakpointsFile(self, file: str, breakpoints: List[SourceBreakpoint]) -> List[BreakpointResult]:
		result = await self.send_request_asyc('setBreakpoints', {
			"source": {
				"path": file
			},
			"breakpoints": json_from_array(SourceBreakpoint.into_json, breakpoints)
		})
		return array_from_json(BreakpointResult.from_json, result['breakpoints'])

	async def ConfigurationDone(self) -> None:
		await self.send_request_asyc('configurationDone', None)

	async def GetVariables(self, variablesReference: int) -> List[Variable]:
		response = await self.send_request_asyc('variables', {
			"variablesReference": variablesReference
		})
		variables = []
		for v in response['variables']:
			var = Variable.from_json(self, v)
			var.containerVariablesReference = variablesReference
			variables.append(var)
		return variables

	def _on_initialized(self) -> None:
		def response(response: dict) -> None:
			pass
		self._on_initialized_future.set_result(None)

	def _on_continued(self, body: dict) -> None:
		threadId = body['threadId']
		self._continued(threadId, body.get('allThreadsContinued', True))

	def _continued(self, threadId: int, allThreadsContinued: bool) -> None:
		if allThreadsContinued:
			self.allThreadsStopped = False

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

		if allThreadsStopped:
			self.allThreadsStopped = True

		event = StoppedEvent(threadId, allThreadsStopped, stopped_text)
		self.events.on_stopped_event(event)

	def _on_terminated(self, body: dict) -> None:
		self.is_running = False
		self.events.on_terminated_event(TerminatedEvent.from_json(body))

	def transport_closed(self) -> None:
		if self.is_running:
			core.log_error('Debug Adapter process was terminated prematurely')
			self._on_terminated({})

	def transport_message(self, message: str) -> None:
		core.log_info('>> ', message)
		msg = json.loads(message)
		self.recieved_msg(msg)

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
		msg = json.dumps(request)
		self.transport.send(msg)
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
		msg = json.dumps(data)
		self.transport.send(msg)

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
				return core.call_soon(self._on_initialized)
			if event == 'output':
				return core.call_soon(self.events.on_output_event, OutputEvent.from_json(event_body))
			if event == 'continued':
				return core.call_soon(self._on_continued, event_body)
			if event == 'stopped':
				return core.call_soon(self._on_stopped, event_body)
			if event == 'terminated':
				return core.call_soon(self._on_terminated, event_body)
			if event == 'thread':
				return core.call_soon(self.events.on_threads_event, ThreadEvent.from_json(event_body))
			if event == 'breakpoint':
				return core.call_soon(self.events.on_breakpoint_event, BreakpointEvent.from_json(event_body))
			if event == 'module':
				return core.call_soon(self.events.on_module_event, ModuleEvent(event_body))
			if event == 'loadedSource':
				return core.call_soon(self.events.on_loaded_source_event, LoadedSourceEvent(event_body))
