'''
	implements the client side of the Debug Adapter protocol

	documentation can be found here
	https://microsoft.github.io/debug-adapter-protocol/specification
	https://microsoft.github.io/debug-adapter-protocol/overview

	a list of server implementers can be found here
	https://microsoft.github.io/debug-adapter-protocol/implementors/adapters/
'''

from debug.core.typecheck import Tuple, List, Optional, Callable, Union, Dict, Any, Generator

import socket
import threading
import json


from debug import ui, core

from debug.libs import asyncio
from debug.main.debug_adapter_client.types import *
from debug.main.debug_adapter_client.transport import Transport

from debug.main.breakpoints import Breakpoints, Breakpoint, BreakpointResult, Filter

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

class DebugAdapterClient:
	def __init__(self, transport: Transport) -> None:
		self.transport = transport
		self.transport.start(self.transport_message, self.transport_closed)
		self.pending_requests = {} #type: Dict[int, Callable[[dict], None]]
		self.seq = 0
		self.frames = [] #type: List[StackFrame]
		self.variables = [] #type: List[Variable]
		self.threads = [] #type: List[Thread]

		self.selected_thread = None #type: Optional[Thread]
		self.selected_frame = None #type: Optional[StackFrame]
		self.stoppedOnError = False
		self.onExited = core.Event() #type: core.Event[Any]
		self.onStopped = core.Event() #type: core.Event[Any]
		self.onContinued = core.Event() #type: core.Event[Any]
		self.onOutput = core.Event() #type: core.Event[Any]
		self.onVariables = core.Event() #type: core.Event[Any]
		self.onThreads = core.Event() #type: core.Event[Any]
		self.on_error_event = core.Event() #type: core.Event[str]
		self.onSelectedStackFrame = core.Event() #type: core.Event[Any]
		self.state = DebuggerState.exited
		self.initialized_future = None #type: Optional[asyncio.Future]
		self.breakpoints_for_id = {} #type: Dict[int, Breakpoint]

	def transport_closed(self) -> None:
		print('Debugger Transport: closed')
		if self.state != DebuggerState.exited:
			self.on_error_event.post('Debug Adapter process was terminated prematurely')
		self._on_exited({})

	def transport_message(self, message: str) -> None:
		msg = json.loads(message)
		core.main_loop.call_soon_threadsafe(self.recieved_msg, msg)

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

	def clear_selection(self) -> None:
		print('clear_selection')
		self.selected_thread = None
		self.selected_frame = None
		self.onSelectedStackFrame.post(None)

	def set_selected_thread_and_frame(self, thread: Thread, frame: StackFrame) -> None:
		print('set_selected_thread_and_frame')
		self.selected_thread = thread
		self.selected_frame = frame
		self.onSelectedStackFrame.post(frame)
		self.scopes(frame.id)

	#FIXME async
	def getStackTrace(self, thread: Thread, response: Callable[[List[StackFrame]], None]) -> None:
		calculateNewSelection = False

		if not self.selected_thread and not self.selected_frame:
			calculateNewSelection = True
		if not self.selected_frame and self.selected_thread and self.selected_thread.id == thread.id:
			calculateNewSelection = True

		def cb(body: dict) -> None:
			frames = []
			foundPrimary = False
			selectedIndex = -1
			for index, frame in enumerate(body['stackFrames']):
				source = frame.get('source')
				hint = frame.get('presentationHint', 'normal')

				if hint == 'label':
					presentation = StackFramePresentation.label
				elif hint == 'subtle':
					presentation = StackFramePresentation.subtle
				else:
					if not foundPrimary:
						foundPrimary = True
						selectedIndex = index
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

			# ensure this thread is still stopped before we select the frame
			# it is possible this thread started running again so we don't want to auto select its frame
			if calculateNewSelection and selectedIndex  >= 0:
				self.set_selected_thread_and_frame(thread, frames[selectedIndex])

			response(frames)

		self.send_request('stackTrace', {
			"threadId" : thread.id
		}, cb)

	def _default_thread_id(self) -> int:
		assert self.threads, 'requires at least one thread?'
		if self.selected_thread:
			return self.selected_thread.id
		return self.threads[0].id

	def scopes(self, frameId: int) -> None:
		def response(response: dict) -> None:
			self.variables.clear()
			for scope in response['scopes']:
				var = Variable(self, scope['name'], '', scope['variablesReference'])
				self.variables.append(var)
			self.onVariables.post(None)
		self.send_request('scopes', {
			"frameId" : frameId
		}, response)
	
	def _thread_for_id(self, id: int) -> Thread:
		for t in self.threads:
			if t.id == id:
				return t
		return Thread(id, '...')

	def threadsCommandBase(self) -> None:
		def response(response: dict) -> None:
			def get_or_create_thread(id: int, name: str) -> Optional[Thread]:
				for t in self.threads:
					if t.id == id:
						t.name = name
						return t
				return Thread(id, name)

			threads = []
			for thread in response['threads']:
				thread = get_or_create_thread(thread['id'], thread['name'])
				threads.append(thread)

			self.threads = threads
			self.onThreads.post(None)

		self.send_request('threads', {}, response)

	@core.async
	def Initialized(self) -> core.awaitable[None]:
		self.initialized_future = core.main_loop.create_future()
		assert self.initialized_future 
		yield from self.initialized_future

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
	def send_request_asyc(self, command: str, data: dict) -> core.awaitable[dict]:
		future = core.main_loop.create_future()
		def response(response: dict) -> None:
			future.set_result(response)
		self.send_request(command, data, response)
		value = yield from future
		return value

	@core.async
	def GetVariables(self, variablesReference: int) -> core.awaitable[List[Variable]]:
		response = yield from self.send_request_asyc('variables', {
			"variablesReference" : variablesReference
		})
		variables = []
		for v in response['variables']:
			var = Variable(self, v['name'], v['value'], v.get('variablesReference', 0))
			variables.append(var)
		return variables

	def _on_initialized(self) -> None:
		def response(response: dict) -> None:
			pass
		assert self.initialized_future, 'expected Initialized() to be called before'
		self.initialized_future.set_result(None)
	
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
		if allThreadsStopped:
			for thread in self.threads:
				thread.stopped = True
				if thread.id == threadId:
					thread.expanded = True
			self.selected_frame = None
		elif not threadId is None:
			thread = self._thread_for_id(threadId)
			thread.stopped = True
			thread.expanded = True

			# clear the selected frame but only if the thread stopped is the one that is already selected
			# when fetching the stack trace we won't select a thread and frame just a new frame on the same thread
			if self.selected_thread and thread.id == self.selected_thread.id:
				self.selected_frame = None

		# we aren't going to post that we changed the threads
		# we will let the threadsCommandBase to that for us so we don't update the UI twice
		self.threadsCommandBase()

		if body.get('allThreadsStopped', True) and body.get('reason', False):
			reason = body.get('reason', '')
			self.stoppedOnError = reason == 'signal' or reason == 'exception'
			
		event = StoppedEvent(body.get('description') or body['reason'], body.get('text'))
		self.onStopped.post(event)

	def _on_exited(self, body: dict) -> None:
		self.state = DebuggerState.exited
		self.onExited.post(None)

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

	def send_request(self, command: str, args: dict, response: Callable[[dict], None]) -> None:
		self.seq += 1
		request = {
			"seq" : self.seq,
			"type" : "request",
			"command": command,
			"arguments" : args
		}
		self.pending_requests[self.seq] = response
		msg = json.dumps(request)
		self.transport.send(msg)
	
	def recieved_msg(self, data: dict) -> None:
		t = data['type']
		if t == 'response':
			body = data.get('body', {})
			callback = self.pending_requests.pop(data['request_seq'])
			callback(body)
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
				return self._on_exited(body)
			if event == 'thread':
				return self._on_thread(body)
			if event == 'breakpoint':
				return self._on_breakpoint(body)