'''
	implements the client side of the Debug Adapter protocol

	documentation can be found here
	https://microsoft.github.io/debug-adapter-protocol/specification
	https://microsoft.github.io/debug-adapter-protocol/overview

	a list of server implementers can be found here
	https://microsoft.github.io/debug-adapter-protocol/implementors/adapters/
'''
from __future__ import annotations
from dataclasses import dataclass
from ..typecheck import *

from ..import core
from .error import Error

import threading


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

	def on_transport_closed(self): ...

@dataclass
class TransportLog:
	out: bool
	data: dict[str, Any]

	def __str__(self) -> str:
		data = self.data
		out = self.out
		type = data.get('type')

		def sigil(success: bool):
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
			return f'{sigil(data.get("success", False))} response/{command}({id}) :: {body}'

		if type == 'request':
			id = data.get('seq')
			command = data.get('command')
			body = data.get('arguments')
			return f'{sigil(True)} request/{command}({id}) :: {body}'

		if type == 'event':
			command = data.get('event')
			body = data.get('body')
			return f'{sigil(True)} event/{command} :: {body}'

		return f'{sigil(False)} {type}/unknown :: {data}'


class TransportProtocol:
	def __init__(
		self,
		transport: Transport,
		events: TransportProtocolListener,
		transport_log: core.Logger,
	) -> None:

		self.events = events
		self.transport_log = transport_log
		self.transport = transport
		self.pending_requests: dict[int, core.Future[dict[str, Any]]] = {}
		self.seq = 0

		self.transport_log.log('transport', f'⟸ process/started ::')
		self.thread = threading.Thread(target=self.read)
		self.thread.start()

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
	def read(self):
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

				core.call_soon_threadsafe(self.recieved_msg, core.json_decode(content))

		except Exception as e:
			core.call_soon_threadsafe(self.transport_log.log,'transport',  f'⟸ process/stopped :: {e}')
			core.call_soon_threadsafe(self.events.on_transport_closed)

	def send(self, message: dict[str, Any]):
		content = core.json_encode(message)
		self.transport.write(bytes(f'Content-Length: {len(content)}\r\n\r\n{content}', 'utf-8'))

	def dispose(self) -> None:
		self.transport.dispose()

	def transport_message(self, message: dict[str, Any]) -> None:
		self.recieved_msg(message)

	def send_request_asyc(self, command: str, args: dict[str, Any]|None) -> Awaitable[dict[str, Any]]:
		future: core.Future[Dict[str, Any]] = core.Future()
		self.seq += 1
		request = {
			'seq': self.seq,
			'type': 'request',
			'command': command,
			'arguments': args
		}

		self.pending_requests[self.seq] = future

		self.log_transport(True, request)
		self.send(request)

		return future

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

		self.log_transport(True, data)
		self.send(data)

	def log_transport(self, out: bool, data: dict[str, Any]):
		self.transport_log.log('transport', TransportLog(out, data))

	@core.schedule
	async def handle_reverse_request(self, request: dict[str, Any]):
		command = request['command']

		try:
			response = await self.events.on_reverse_request(command, request.get('arguments', {}))
			self.send_response(request, response)
		except core.Error as e:
			self.send_response(request, {}, error=str(e))

	def recieved_msg(self, data: dict[str, Any]) -> None:
		t = data['type']
		self.log_transport(False, data)

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
			core.call_soon(self.handle_reverse_request, data)

		if t == 'event':
			event_body: dict[str, Any] = data.get('body', {})
			event = data['event']

			# use call_soon so that events and respones are handled in the same order as the server sent them
			core.call_soon(self.events.on_event, event, event_body)

