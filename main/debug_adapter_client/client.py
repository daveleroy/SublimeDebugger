'''
	implements the client side of the Debug Adapter protocol

	documentation can be found here
	https://microsoft.github.io/debug-adapter-protocol/specification
	https://microsoft.github.io/debug-adapter-protocol/overview

	a list of server implementers can be found here
	https://microsoft.github.io/debug-adapter-protocol/implementors/adapters/
'''

from sublime_db.core.typecheck import Tuple, List, Optional, Callable, Union, Dict, Any, Generator

import socket
import threading
import json


from sublime_db.libs import asyncio
from sublime_db import ui, core
from sublime_db.main.breakpoints import Breakpoints, Breakpoint, BreakpointResult, Filter

from .types import StackFrame, StackFramePresentation, Variable, Thread, Scope, EvaluateResponse, CompletionItem
from .transport import Transport

class DebuggerState:
	exited = 1
	stopped = 2
	running = 3

class StoppedEvent:
	def __init__(self, reason: str, text: Optional[str]) -> None:
		self.reason = reason
		self.text = text

class OutputEvent:
	def __init__(self, category: str, text: str, variablesReference: int) -> None:
		self.category = category
		self.text = text
		self.variablesReference = variablesReference

@core.all_methods(core.require_main_thread)
class DebugAdapterClient:
	def __init__(self, transport: Transport) -> None:
		self.transport = transport
		self.transport.start(self.transport_message, self.transport_closed)
		self.pending_requests = {} #type: Dict[int, core.future]
		self.seq = 0
		self.frames = [] #type: List[StackFrame]
		self.scopes = [] #type: List[Scope]

		self.threads = [] #type: List[Thread]
		self.threads_for_id = {} #type: Dict[int, Thread]

		self.selected_thread = None #type: Optional[Thread]
		self.selected_frame = None #type: Optional[StackFrame]
		self.stoppedOnError = False
		self.onExited = core.Event() #type: core.Event[Any]
		self.onStopped = core.Event() #type: core.Event[Any]
		self.onContinued = core.Event() #type: core.Event[Any]
		self.onOutput = core.Event() #type: core.Event[Any]
		self.onScopes = core.Event() #type: core.Event[Any]
		self.onThreads = core.Event() #type: core.Event[Any]
		self.on_error_event = core.Event() #type: core.Event[str]
		self.onSelectedStackFrame = core.Event() #type: core.Event[Any]
		self.state = DebuggerState.exited
		self._on_initialized_future = core.main_loop.create_future()
		self._on_terminated_future = core.main_loop.create_future()
		self.breakpoints_for_id = {} #type: Dict[int, Breakpoint]

	def transport_closed(self) -> None:
		print('Debugger Transport: closed')
		if self.state != DebuggerState.exited:
			self.on_error_event.post('Debug Adapter process was terminated prematurely')
			self._on_terminated({})

	def transport_message(self, message: str) -> None:
		print('>> ', message)
		msg = json.loads(message)
		self.recieved_msg(msg)

	def dispose(self) -> None:
		print('disposing Debugger')
		self.transport.dispose()

	@core.async
	def StepIn(self) -> core.awaitable[None]:
		yield from self.send_request_asyc('stepIn', {
			'threadId' : self._default_thread_id()
		})
	@core.async
	def StepOut(self) -> core.awaitable[None]:
		yield from self.send_request_asyc('stepOut', {
			'threadId' : self._default_thread_id()
		})
	@core.async
	def StepOver(self) -> core.awaitable[None]:
		yield from self.send_request_asyc('next', {
			'threadId' : self._default_thread_id()
		})
	@core.async
	def Resume(self, thread : Optional[Thread] = None) -> core.awaitable[None]:
		print('continue!')
		if thread:
			thread_id = thread.id
		else:
			thread_id = self._default_thread_id()
		print('continue!')
		body = yield from self.send_request_asyc('continue', {
			'threadId' : thread_id
		})
		print('continued!')
		self._continued(thread_id, body.get('allThreadsContinued', True))

	@core.async
	def Pause(self) -> core.awaitable[None]:
		yield from self.send_request_asyc('pause', {
			'threadId' : self._default_thread_id()
		})
		
	@core.async
	def Disconnect(self) -> core.awaitable[None]:
		yield from self.send_request_asyc('disconnect', {
		})
		yield from self._on_terminated_future

	def clear_selection(self) -> None:
		print('clear_selection')
		self.selected_thread = None
		self.selected_frame = None
		self.onSelectedStackFrame.post(None)

	def set_selected_thread_and_frame(self, thread: Thread, frame: StackFrame) -> None:
		print('set_selected_thread_and_frame')
		assert thread
		assert frame
		self.selected_thread = thread
		self.selected_frame = frame
		self.onSelectedStackFrame.post(frame)

		def response(response: dict) -> None:
			self.scopes.clear()
			for scope in response['scopes']:
				var = Scope.from_json(self, scope)
				self.scopes.append(var)
			self.onScopes.post(None)

		core.run(self.send_request_asyc('scopes', {
			"frameId" : frame.id
		}), response)

	#FIXME async
	def getStackTrace(self, thread: Thread, response: Callable[[List[StackFrame]], None]) -> None:
		selection_in_other_thread = False
		selected_frame_id = -1

		if self.selected_thread:
			assert self.selected_frame
			if self.selected_thread.id == thread.id:
				selected_frame_id = self.selected_frame.id
			else:
				selection_in_other_thread = True

		def cb(body: dict) -> None:
			frames = []
			default_selected_index = -1
			found_selected_frame = False

			for index, frame in enumerate(body['stackFrames']):
				source = frame.get('source')
				hint = frame.get('presentationHint', 'normal')

				if hint == 'label':
					presentation = StackFramePresentation.label
				elif hint == 'subtle':
					presentation = StackFramePresentation.subtle
				else:
					if default_selected_index < 0:
						default_selected_index = index
					presentation = StackFramePresentation.normal
				internal = False

				file = None
				if source:
					file = source.get('path')
				if not file:
					file = '??'
					internal = True
				frame = StackFrame(frame['id'], file, frame['name'], frame.get('line', 0), internal, presentation)
				frames.append(frame)
				if frame.id == selected_frame_id:
					found_selected_frame = True

			# we auto select a frame if we don't already have a frame selected in another thread
			# if the frame selected is in our thread but we didn't find the same frame then we select a new one
			
			# ensure this thread is still stopped before we select the frame
			# it is possible this thread started running again so we don't want to auto select its frame
			if thread.stopped and not selection_in_other_thread and not found_selected_frame:
				self.set_selected_thread_and_frame(thread, frames[default_selected_index])

			response(frames)

		core.run(self.send_request_asyc('stackTrace', {
			"threadId" : thread.id
		}), cb)

	def _default_thread_id(self) -> int:
		assert self.threads, 'requires at least one thread?'
		if self.selected_thread:
			return self.selected_thread.id
		return self.threads[0].id		
	
	def _thread_for_id(self, id: int) -> Thread:
		thread = self.threads_for_id.get(id)
		if thread:
			return thread

		thread = Thread(id, '...')
		self.threads_for_id[id] = thread
		return thread

	def threadsCommandBase(self) -> None:
		def response(response: dict) -> None:
			def get_or_create_thread(id: int, name: str) -> Optional[Thread]:
				thread = self._thread_for_id(id)
				thread.name = name
				return thread
			
			threads = []
			for thread in response['threads']:
				thread = get_or_create_thread(thread['id'], thread['name'])
				threads.append(thread)

			self.threads = threads
			self.onThreads.post(None)

		core.run(self.send_request_asyc('threads', {}), response)

	@core.async
	def Initialized(self) -> core.awaitable[None]:
		yield from self._on_initialized_future

	@core.async
	def Evaluate(self, expression: str, context: Optional[str]) -> core.awaitable[Optional[EvaluateResponse]]:
		frameId = None #type: Optional[int]
		if self.selected_frame:
			frameId = self.selected_frame.id

		response = yield from self.send_request_asyc("evaluate", {
			"expression" : expression,
			"context" : context,
			"frameId" : frameId,
		})

		# the spec doesn't say this is optional? does this mean some implementations throw errors and others return a null result?
		if response['result'] is None:
			return None
		# variablesReference doesn't appear to be optional in the spec... but some adapters treat it as such
		return EvaluateResponse(response["result"], response.get("variablesReference", 0))

	
	@core.async
	def Completions(self, text: str, column: int) -> core.awaitable[List[CompletionItem]]:
		frameId = None
		if self.selected_frame:
			frameId = self.selected_frame.id

		response = yield from self.send_request_asyc("completions", {
			"frameId" : frameId,
			"text" : text,
			"column" : column,
		})
		items = [] #type: List[CompletionItem]
		for item in response['targets']:
			items.append(CompletionItem.from_json(item))
		return items

	@core.async
	def setVariable(self, variable: Variable, value: str) -> core.awaitable[Variable]:
		response = yield from self.send_request_asyc("setVariable", {
			"variablesReference" : variable.containerVariablesReference,
			"name" : variable.name,
			"value" : value,
		})
		
		variable.value = response['value']
		variable.variablesReference = response.get('variablesReference', 0)
		return variable

	@core.async
	def Initialize(self) -> core.awaitable[dict]:
		response = yield from self.send_request_asyc("initialize", {
			"clientID":"sublime",
			"clientName":"Sublime Text",
			"adapterID":"python",
			"pathFormat":"path",
			"linesStartAt1":True,
			"columnsStartAt1":True,
			"supportsVariableType": True,
			"supportsVariablePaging": False,
			"supportsRunInTerminalRequest": False,
			"locale":"en-us"}
		)
		return response

	@core.async
	def Launch(self, config: dict) -> core.awaitable[None]:
		yield from self.send_request_asyc('launch', config)
		# the spec says to grab the baseline threads here?
		self.threadsCommandBase()
		self.state = DebuggerState.running
		self.onContinued.post(None)

	@core.async
	def Attach(self, config: dict) -> core.awaitable[None]:
		yield from self.send_request_asyc('attach', config)
		# the spec says to grab the baseline threads here?
		self.threadsCommandBase()
		self.state = DebuggerState.running
		self.onContinued.post(None)

	@core.async
	def setExceptionBreakpoints(self, filters: List[Filter]) -> core.awaitable[None]:
		ids = []
		for f in filters:
			if not f.enabled:
				continue
			ids.append(f.id)

		yield from self.send_request_asyc('setExceptionBreakpoints', {
			'filters' : ids
		})
	@core.async
	def SetBreakpointsFile(self, file: str, breakpoints: List[Breakpoint]) -> core.awaitable[None]:
		sourceBreakpoints = [] #type: List[dict]
		breakpoints = list(filter(lambda b: b.enabled, breakpoints))
		for breakpoint in breakpoints:
			sourceBreakpoint = {
				"line" : breakpoint.line
			} #type: dict
			if breakpoint.log:
				sourceBreakpoint["logMessage"] = breakpoint.log
			if breakpoint.condition:
				sourceBreakpoint["condition"] = breakpoint.condition
			if breakpoint.count:
				sourceBreakpoint["hitCondition"] = str(breakpoint.count)
			sourceBreakpoints.append(sourceBreakpoint)
		
		try:
			result = yield from self.send_request_asyc('setBreakpoints', {
				"source" : {
					"path" : file
				},
				"breakpoints" : sourceBreakpoints
			})
			breakpoints_result = result['breakpoints']
			assert len(breakpoints_result) == len(breakpoints), 'expected #breakpoints to match results'
			for breakpoint, breakpoint_result in zip(breakpoints, breakpoints_result):
				self._merg_breakpoint(breakpoint, breakpoint_result)
				id = breakpoint_result.get('id')
				if not id is None:
					self.breakpoints_for_id[id] = breakpoint

		except Exception as e:
			for breakpoint in breakpoints:
				result = BreakpointResult(False, breakpoint.line, str(e))
				self.breakpoints.set_breakpoint_result(breakpoint, result)
				
			raise e #re raise the exception

	def _merg_breakpoint(self, breakpoint: Breakpoint, breakpoint_result: dict) -> None:
		result = BreakpointResult(breakpoint_result['verified'], breakpoint_result.get('line', breakpoint.line), breakpoint_result.get('message'))
		self.breakpoints.set_breakpoint_result(breakpoint, result)

	@core.async
	def AddBreakpoints(self, breakpoints: Breakpoints) -> core.awaitable[None]:
		self.breakpoints = breakpoints
		requests = [] #type: List[core.awaitable[dict]]
		bps = {} #type: Dict[str, List[Breakpoint]]
		for breakpoint in breakpoints.breakpoints:
			if breakpoint.file in bps:
				bps[breakpoint.file].append(breakpoint)
			else:
				bps[breakpoint.file] = [breakpoint]
			
			print(breakpoint, breakpoint.file)

		print('breakpoints:', bps)
		for file, filebreaks in bps.items():
			requests.append(self.SetBreakpointsFile(file, filebreaks))

		filters = []
		for filter in breakpoints.filters:
			if filter.enabled:
				filters.append(filter.id)

		requests.append(self.send_request_asyc('setExceptionBreakpoints', {
			'filters' : filters
		}))
		if requests:
			yield from asyncio.wait(requests)

	@core.async
	def ConfigurationDone(self) -> core.awaitable[None]:
		print('Configuration done!')
		yield from self.send_request_asyc('configurationDone', {})

	@core.async
	def GetVariables(self, variablesReference: int) -> core.awaitable[List[Variable]]:
		response = yield from self.send_request_asyc('variables', {
			"variablesReference" : variablesReference
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
	
	def _continued(self, threadId: int, allThreadsContinued: bool) -> None:
		if allThreadsContinued:
			self.state = DebuggerState.running

		if allThreadsContinued:
			self.clear_selection()
			for thread in self.threads:
				thread.stopped = False

		else:
			thread = self._thread_for_id(threadId)
			if self.selected_thread and threadId == self.selected_thread.id:
				self.clear_selection()
			thread.stopped = False
			
		# we have to post that we changed the threads here
		self.onThreads.post(None)
		self.onContinued.post(None)
	def _on_continued(self, body: dict) -> None:
		threadId = body['threadId']
		self._continued(threadId, body.get('allThreadsContinued', True))

	def _on_stopped(self, body: dict) -> None:
		self.state = DebuggerState.stopped
		#only ask for threads if there was a reason for the stoppage
		threadId = body.get('threadId', None)
		allThreadsStopped = body.get('allThreadsStopped', False)

		thread_for_event = self._thread_for_id(threadId)
		thread_for_event.stopped = True
		thread_for_event.expanded = True

		if allThreadsStopped:
			for thread in self.threads:
				thread.stopped = True
			self.clear_selection()
		else:
			# clear the selected frame but only if the thread stopped is the one that is already selected
			if self.selected_thread and thread_for_event.id == self.selected_thread.id:
				self.clear_selection()

		# we aren't going to post that we changed the threads
		# we will let the threadsCommandBase to that for us so we don't update the UI twice
		self.threadsCommandBase()

		if allThreadsStopped and body.get('reason', False):
			reason = body.get('reason', '')
			self.stoppedOnError = reason == 'signal' or reason == 'exception'
			
		event = StoppedEvent(body.get('description') or body['reason'], body.get('text'))
		self.onStopped.post(event)

	def _on_terminated(self, body: dict) -> None:
		self.state = DebuggerState.exited
		self.onExited.post(None)
		self._on_terminated_future.set_result(None)
	def _on_output(self, body: dict) -> None:
		category = body.get('category', 'console')
		data = OutputEvent(category, body['output'], body.get('variablesReference', 0))
		self.onOutput.post(data)

	def _on_thread(self, body: dict) -> None:
		self.threadsCommandBase()

	def _on_breakpoint(self, body: dict) -> None:
		breakpoint_result = body['breakpoint']
		id = breakpoint_result.get('id')
		if id is None:
			return
		breakpoint = self.breakpoints_for_id.get(id)
		if not breakpoint:
			return
		self._merg_breakpoint(breakpoint, breakpoint_result)

	@core.async
	def send_request_asyc(self, command: str, args: dict) -> core.awaitable[dict]:
		future = core.main_loop.create_future()
		self.seq += 1
		request = {
			"seq" : self.seq,
			"type" : "request",
			"command": command,
			"arguments" : args
		}
		self.pending_requests[self.seq] = future
		msg = json.dumps(request)
		self.transport.send(msg)

		value = yield from future
		return value
	
	def recieved_msg(self, data: dict) -> None:
		t = data['type']
		if t == 'response':
			future = self.pending_requests.pop(data['request_seq'])

			success = data['success']
			if not success:
				future.set_exception(Exception(data.get('message', 'no error message')))

			body = data.get('body', {})
			future.set_result(body)
			return
		if t == 'event':
			body = data.get('body', {})
			event = data['event']
			if event == 'initialized':
				return self._on_initialized()
			if event == 'output':
				return self._on_output(body)
			if event == 'continued':
				return self._on_continued(body)
			if event == 'stopped':
				return self._on_stopped(body)
			if event == 'terminated':
				return self._on_terminated(body)
			if event == 'thread':
				return self._on_thread(body)
			if event == 'breakpoint':
				return self._on_breakpoint(body)