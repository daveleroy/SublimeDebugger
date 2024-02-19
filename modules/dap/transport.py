'''
	implements the client side of the Debug Adapter protocol

	documentation can be found here
	https://microsoft.github.io/debug-adapter-protocol/specification
	https://microsoft.github.io/debug-adapter-protocol/overview

	a list of server implementers can be found here
	https://microsoft.github.io/debug-adapter-protocol/implementors/adapters/
'''
from __future__ import annotations
from typing import Any, Awaitable, Protocol

from .configuration import ConfigurationExpanded

from ..import core
from .error import Error

import threading
from dataclasses import dataclass


class TransportConnectionError(core.Error):
	...

class Transport:
	async def start(self, listener: TransportListener, configuration: ConfigurationExpanded, log: core.Logger):
		...
	def dispose(self) -> None:
		...
	def send_request(self, command: str, args: core.JSON|None) -> Awaitable[core.JSON]:
		...
	def send_event(self, event: str, body: core.JSON) -> None:
		...
	def send_response(self, request: core.JSON, body: core.JSON, error: str|None = None) -> None:
		...

class TransportListener (Protocol):
	def on_event(self, event: str, body: core.JSON):
		...
	async def on_reverse_request(self, command: str, arguments: core.JSON) -> core.JSON:
		...

	def on_transport_closed(self) -> Any: ...


@dataclass
class TransportOutputLog:
	type: str
	output: str
	def __str__(self) -> str:
		return f'-> {type} :: {self.output}'

@dataclass
class TransportDataLog:
	data: dict[str, Any]

	def __str__(self) -> str:
		data: dict[str, Any] = self.data
		data_formatted = core.json_encode(data)

		type = data.get('type')

		def sigil(success: bool):
			if success:
				return '::'
			else:
				return '!!'

		if type == 'response':
			id = data.get('request_seq')
			command = data.get('command')
			return f'{command}({id}) {sigil(data.get("success", False))} {data_formatted}'

		if type == 'request':
			id = data.get('seq')
			command = data.get('command')
			return f'{command}({id}) :: {data_formatted}'

		if type == 'event':
			command = data.get('event')

			return f'{command} .. {data_formatted}'

		return f'unknown :: {data_formatted}'

class TransportIncomingDataLog(TransportDataLog):
	data: dict[str, Any]

	def __str__(self) -> str:
		return '-> ' + super().__str__()

class TransportOutgoingDataLog(TransportDataLog):
	data: dict[str, Any]

	def __str__(self) -> str:
		return '<- ' + super().__str__()

class TransportStream(Transport):
	def write(self, message: bytes):
		...
	def readline(self) -> bytes:
		...
	def read(self, n: int) -> bytes:
		...

	async def setup(self):
		...

	async def start(self, listener: TransportListener, configuration: ConfigurationExpanded, log: core.Logger):
		self.events = listener
		self.configuration = configuration
		self.log = log

		self.pending_requests: dict[int, core.Future[core.JSON]] = {}
		self.seq = 0

		self.log('transport', f'-- begin transport protocol')

		await self.setup()

		self.thread = threading.Thread(target=self.read_transport, name='dap')
		self.thread.start()

	def dispose(self):
		...

	# Content-Length: 119\r\n
	# \r\n
	# {
	#     "seq": 153,
	#     "type": "request",
	#     "command": "next",
	#     "arguments": {
	#         "threadId": 3
	#     }
	# }
	def read_transport(self):
		header = b'Content-Length: '
		header_length = len(header)

		try:
			while True:
				# handle Content-Length: 119\r\n
				line = self.readline()
				if not header.startswith(header):
					core.error('Expecting Content-Length: header but did not...')
					continue

				size = int(line[header_length:].strip())

				#handle \r\n
				line = self.readline()
				if line != b'\r\n':
					core.error('Expected \\n\\r but did not find...')
					core.error(line)
					continue


				# read message
				content = b''
				while len(content) != size:
					bytes_left = size - len(content)
					content += self.read(bytes_left)

				self.on_message(core.json_decode(content))

		except Exception as e:
			msg = '-- end transport protocol: ' + (str(e) or 'eof')
			core.call_soon(self.on_closed, msg)

	def send(self, message: dict[str, Any]):
		content = core.json_encode(message)
		self.write(bytes(f'Content-Length: {len(content)}\r\n\r\n{content}', 'utf-8'))

	def send_request(self, command: str, args: core.JSON|None) -> Awaitable[core.JSON]:
		future: core.Future[core.JSON] = core.Future()
		self.seq += 1
		request = {
			'seq': self.seq,
			'type': 'request',
			'command': command,
			'arguments': args
		}

		self.pending_requests[self.seq] = future

		self.log('transport', TransportOutgoingDataLog(request))
		self.send(request)
		return future


	def send_event(self, event: str, body: core.JSON) -> None:
		self.seq += 1

		data = {
			'type': 'event',
			'event': event,
			'seq': self.seq,
			'body': body,
		}

		self.log('transport', TransportOutgoingDataLog(data))
		self.send(data)

	def send_response(self, request: core.JSON, body: core.JSON, error: str|None = None) -> None:
		self.seq += 1

		if error:
			success = False
		else:
			success = True

		data = {
			'type': 'response',
			'seq': self.seq,
			'request_seq': request['seq'],
			'command': request['command'],
			'body': body,
			'success': success,
			'message': error,
		}

		self.log('transport', TransportOutgoingDataLog(data))
		self.send(data)

	def on_request(self, request: core.JSON):
		command = request['command']

		@core.run
		async def r():
			try:
				response = await self.events.on_reverse_request(command, request.get('arguments', {}))
				self.send_response(request, response)
			except core.Error as e:
				self.send_response(request, core.JSON(), error=str(e))

		r()


	def on_event(self, event: str, body: Any):
		# use call_soon so that events and respones are handled in the same order as the server sent them
		core.call_soon(self.events.on_event, event, body)

	def on_closed(self, msg: str) -> None:
		self.log('transport', msg)

		# use call_soon so that events and respones are handled in the same order as the server sent them
		core.call_soon(self.events.on_transport_closed)

	def on_message(self, data: core.JSON) -> None:
		self.log('transport', TransportIncomingDataLog(data))

		t = data['type']
		if t == 'response':
			try:
				future = self.pending_requests.pop(data['request_seq'])
			except KeyError:
				# the python adapter seems to send multiple initialized responses?
				core.info("ignoring request request_seq not found")
				return

			success = data['success']
			if not success:
				body: core.JSON = data.get('body', {})
				if error := body.get('error'):
					future.set_exception(Error.from_message(error))
					return

				future.set_exception(Error(data.get('message', 'no error message')))
				return
			else:
				body: core.JSON = data.get('body', {})
				future.set_result(body)
			return

		if t == 'request':
			self.on_request(data)

		if t == 'event':
			self.on_event(data['event'], data.get('body', {}))
