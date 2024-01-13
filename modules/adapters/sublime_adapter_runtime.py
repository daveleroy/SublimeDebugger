import json
import sublime
import sublime_plugin

import os
import sys
import threading
import builtins
import inspect

import debugpy
from debugpy._vendored.pydevd import pydevd


os.environ['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'


configuration = sublime.decode_value(os.environ['sublime_debug_configuration'])

if sys.version_info >= (3, 8):
	host_name = 'plugin_host_38'
	port = configuration['port_38']
else:
	host_name = 'plugin_host_33'
	port = configuration['port_33']


class SublimeDebugRuntimeClient(pydevd.IDAPMessagesListener):
	def __init__(self, name, port) -> None:
		debugpy.connect(port)

		pydevd.add_dap_messages_listener(self)

		debugpy.wait_for_client()
		sublime.set_timeout_async(lambda: self.attach_to_thread('AsyncThread'))


	def attach_to_thread(self, name: str):
		threading.current_thread().setName(name)
		debugpy.trace_this_thread(True)

	def before_send(self, message_as_dict):
		...

	def after_receive(self, message_as_dict):
		if message_as_dict.get('command') == 'reload':
			sublime_plugin.reload_plugin(message_as_dict['arguments']['entry'])


client = SublimeDebugRuntimeClient(host_name, port)
