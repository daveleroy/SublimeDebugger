from __future__ import annotations
from typing import Any

import sublime
import sublime_plugin
from ...import core

_futures: dict[int, core.Future] = {}	

class TimedOut(core.Error): ...

class DebuggerBridgeCommand(sublime_plugin.WindowCommand):
	@staticmethod
	async def request(command:str, **kwargs):
		'''
		Returns the response or raises an exception.
		'''
		future = core.Future()
		_id = id(future)
		_futures[_id] = future

		# NOTE: the active window might not match the debugger window but generally will
		# TODO: a way to get the actual window.
		data = {'id': _id }
		for key in kwargs:
			data[key] = kwargs[key]

		def timeout():
			if not future.done():
				future.set_exception(TimedOut(f'{command} timed out'))

		sublime.set_timeout(timeout, 10 * 1000)
		sublime.active_window().run_command(command, data)
		
		try:
			command_response = await future
		finally:
			del _futures[_id]

		if 'resolve' in command_response:
			return command_response['resolve']

		raise core.Error(command_response.get('reject') or 'Expected `resolve` or `reject`')

	def run(self, id, **args): #type: ignore
		_futures[id].set_result(args)
