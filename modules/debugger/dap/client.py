'''
	implements the client side of the Debug Adapter protocol

	documentation can be found here
	https://microsoft.github.io/debug-adapter-protocol/specification
	https://microsoft.github.io/debug-adapter-protocol/overview

	a list of server implementers can be found here
	https://microsoft.github.io/debug-adapter-protocol/implementors/adapters/
'''

from ... typecheck import *

import json
import threading

from ... import core

from .types import *


class Transport(Protocol):
	def write(self, message: bytes) -> None:
		...
	def readline(self) -> bytes:
		...
	def read(self, n: int) -> bytes:
		...
	def dispose(self) ->None:
		...

class ClientEventsListener (Protocol):
	# reverse requests
	def on_event(self, name: str, data: dict):
		...

	async def on_reverse_request(self, name: str, data: dict) -> dict:
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
		self.transport = transport
		self.pending_requests = {} #type: Dict[int, core.future]
		self.seq = 0

		self.transport_log.info(f'⟸ process/started')
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
					print('Expecting Content-Length: header but did not...')
					continue

				size = int(line[header_length:].strip())

				#handle \r\n
				line = self.transport.readline()
				if line != b'\r\n':
					print('Expected \\n\\r but did not find...')
					print(line)
					continue


				# read message
				content = b''
				while len(content) != size:
					bytes_left = size - len(content)
					content += self.transport.read(bytes_left)


				json_message = json.loads(content)
				core.call_soon_threadsafe(self.recieved_msg, json_message)

		except Exception as e:
			core.call_soon_threadsafe(self.transport_log.info, f'⟸ process/closed :: {e}')
			core.call_soon_threadsafe(self.events.on_event, "terminated", {})

	def send(self, message):
		content = json.dumps(message)
		self.transport.write(bytes(f'Content-Length: {len(content)}\r\n\r\n{content}', 'utf-8'))

	def dispose(self) -> None:
		self.transport.dispose()

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
		self.send(request)

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
		self.send(data)

	def log_transport(self, out: bool, data: dict):
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
			self.transport_log.info(f'{sigil(data.get("success", False))} response/{command}({id}) :: {body}')
			return

		if type == 'request':
			id = data.get('seq')
			command = data.get('command')
			body = data.get('arguments')
			self.transport_log.info(f'{sigil(True)} request/{command}({id}) :: {body}')
			return

		if type == 'event':
			command = data.get('event')
			body = data.get('body')
			self.transport_log.info(f'{sigil(True)} event/{command} :: {body}')
			return

		self.transport_log.info(f'{sigil(False)} {type}/unknown :: {data}')

	@core.schedule
	async def handle_reverse_request(self, request: dict):
		command = request['command']

		try:
			response = await self.events.on_reverse_request(command, request.get('arguments', {}))
			self.send_response(request, response)
		except core.Error as e:
			self.send_response(request, {}, error=str(e))

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
			core.call_soon(self.handle_reverse_request, data)

		if t == 'event':
			event_body = data.get('body', {})
			event = data['event']

			# use call_soon so that events and respones are handled in the same order as the server sent them
			core.call_soon(self.events.on_event, event, event_body)

