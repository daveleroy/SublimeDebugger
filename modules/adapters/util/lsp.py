from __future__ import annotations
from typing import Any

import sublime
import sublime_plugin
from ...import core

_futures: dict[int, core.Future] = {}	

async def request(session_name: str, method: str, params: Any) -> Any:
	'''
	Returns the response or raises an exception.
	'''
	future = core.Future()
	_id = id(future)
	_futures[_id] = future

	# Send a request to Metals.
	# NOTE: the active window might not match the debugger window but generally will
	# TODO: a way to get the actual window.
	sublime.active_window().run_command(
		'debugger_lsp_bridge_request', 
		{'id': _id, 'session_name': session_name, 'method': method, 'params': params}
	)
	sublime.set_timeout(lambda: future.cancel(), 2500)
	try:
		command_response = await future
	except core.CancelledError:
		raise core.Error('Unable to connect to LSP client (timed out)') from None
	finally:
		del _futures[_id]


	if resolve := command_response.get('resolve'):
		return resolve

	raise core.Error(command_response.get('reject') or 'Expected `resolve` or `reject`')



class DebuggerLspBridgeResponseCommand(sublime_plugin.WindowCommand):
	def run(self, id, **args):
		_futures[id].set_result(args)
