import sublime
import sublime_plugin

import os
import socket
import sys
import threading
import builtins
import inspect

import debugpy



if sys.version_info >= (3, 8):
	host_name = 'plugin_host_38'
	port = int(os.environ['sublime_debug_port_38'])
else:
	host_name = 'plugin_host_33'
	port = int(os.environ['sublime_debug_port_33'])


class SublimeDebugRuntimeClient:
	def __init__(self, name, port) -> None:
		debugpy.configure()
		debugpy.connect(port)
		sublime.set_timeout_async(lambda: self.attach_to_thread('AsyncThread'))
		debugpy.wait_for_client()



	def attach_to_thread(self, name: str):
		threading.current_thread().setName(name)
		debugpy.trace_this_thread(True)

client = SublimeDebugRuntimeClient(host_name, port)
