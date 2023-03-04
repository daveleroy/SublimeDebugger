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

from ..import core
from .error import Error

import threading
from dataclasses import dataclass


class Transport(Protocol):
	def write(self, message: bytes):
		...
	def readline(self) -> bytes:
		...
	def read(self, n: int) -> bytes:
		...
	def dispose(self):
		...

class TransportProtocolListener (Protocol):
	def on_event(self, event: str, body: dict[str, Any]):
		...
	async def on_reverse_request(self, command: str, arguments: dict[str, Any]) -> dict[str, Any]:
		...

	def on_transport_closed(self) -> Any: ...


@dataclass
class TransportStdoutOutputLog:
	output: str
	def __str__(self) -> str:
		return '-> stdout :: ' + self.output

@dataclass
class TransportStderrOutputLog:
	output: str
	def __str__(self) -> str:
		return '-> stderr !! ' + self.output

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


class TransportProtocol:
	def __init__(self, transport: Transport) -> None:
		self.transport = transport

	def start(self, listener: TransportProtocolListener, log: core.Logger):
		self.events = listener
		self.log = log

		self.pending_requests: dict[int, core.Future[dict[str, Any]]] = {}
		self.seq = 0

		self.log.log('transport', f'-- begin transport protocol')
		self.thread = threading.Thread(target=self.read_transport, name='dap')
		self.thread.start()

	def dispose(self) -> None:
		self.transport.dispose()

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
				line = self.transport.readline()
				if not header.startswith(header):
					core.error('Expecting Content-Length: header but did not...')
					continue

				size = int(line[header_length:].strip())

				#handle \r\n
				line = self.transport.readline()
				if line != b'\r\n':
					core.error('Expected \\n\\r but did not find...')
					core.error(line)
					continue


				# read message
				content = b''
				while len(content) != size:
					bytes_left = size - len(content)
					content += self.transport.read(bytes_left)

				self.on_message(core.json_decode(content))

		except Exception as e:
			msg = '-- end transport protocol: ' + (str(e) or 'eof')
			core.call_soon(self.on_closed, msg)

	def send(self, message: dict[str, Any]):
		content = core.json_encode(message)
		self.transport.write(bytes(f'Content-Length: {len(content)}\r\n\r\n{content}', 'utf-8'))

	def send_request(self, command: str, args: dict[str, Any]|None) -> Awaitable[dict[str, Any]]:
		future: core.Future[dict[str, Any]] = core.Future()
		self.seq += 1
		request = {
			'seq': self.seq,
			'type': 'request',
			'command': command,
			'arguments': args
		}

		self.pending_requests[self.seq] = future

		self.log.log('transport', TransportOutgoingDataLog(request))
		self.send(request)
		return future


	def send_event(self, event: str, body: dict[str, Any]) -> None:
		self.seq += 1

		data = {
			'type': 'event',
			'event': event,
			'seq': self.seq,
			'body': body,
		}

		self.log.log('transport', TransportOutgoingDataLog(data))
		self.send(data)

	def send_response(self, request: dict[str, Any], body: dict[str, Any], error: str|None = None) -> None:
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

		self.log.log('transport', TransportOutgoingDataLog(data))
		self.send(data)

	def on_request(self, request: dict[str, Any]):
		command = request['command']

		@core.run
		async def r():
			try:
				response = await self.events.on_reverse_request(command, request.get('arguments', {}))
				self.send_response(request, response)
			except core.Error as e:
				self.send_response(request, {}, error=str(e))

		r()


	def on_event(self, event: str, body: Any):
		# use call_soon so that events and respones are handled in the same order as the server sent them
		core.call_soon(self.events.on_event, event, body)

	def on_closed(self, msg: str) -> None:
		self.log.log('transport', msg)

		# use call_soon so that events and respones are handled in the same order as the server sent them
		core.call_soon(self.events.on_transport_closed)

	def on_message(self, data: dict[str, Any]) -> None:
		self.log.log('transport', TransportIncomingDataLog(data))

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
				body: dict[str, Any] = data.get('body', {})
				if error := body.get('error'):
					future.set_exception(Error.from_message(error))
					return

				future.set_exception(Error(data.get('message', 'no error message')))
				return
			else:
				body: dict[str, Any] = data.get('body', {})
				future.set_result(body)
			return

		if t == 'request':
			self.on_request(data)

		if t == 'event':
			self.on_event(data['event'], data.get('body', {}))
