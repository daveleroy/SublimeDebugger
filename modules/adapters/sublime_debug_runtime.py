import sublime
import sublime_plugin

import os
import socket
import sys
import threading
import builtins
import inspect

import debugpy


sublime_debug_runtime_port = int(os.environ['sublime_debug_runtime_port'])

host_name = 'plugin_host_38' if sys.version_info >= (3, 8) else 'plugin_host_33'


class SublimeDebugRuntimeClient:
	def __init__(self, name, port) -> None:
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect(('localhost', port))
		self.socket_file = self.socket.makefile('wr')

		debugpy.configure(python='python3')
		address = debugpy.listen(0)
		sublime.set_timeout_async(lambda: self.attach_to_thread('AsyncThread'))

		self.send({
			'event': 'attach',
			'body': {
				'name': name,
				'host': address[0],
				'port': address[1],
			}
		})

		debugpy.wait_for_client()


	def attach_to_thread(self, name: str):
		threading.current_thread().setName(name)
		debugpy.trace_this_thread(True)


	def send(self, json):
		self.socket_file.write(sublime.encode_value(json))
		self.socket_file.write('\n')
		self.socket_file.flush()

client = SublimeDebugRuntimeClient(host_name, sublime_debug_runtime_port)

