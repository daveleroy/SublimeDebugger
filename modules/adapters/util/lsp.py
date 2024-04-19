from typing import Any

import sublime
from ... import core

async def request(session_name: str, method: str, params: Any) -> Any:
	try:
		from LSP.plugin import Request, LspWindowCommand
	except ImportError:
		raise core.Error('This debug adapter requires LSP which does not appear to be installed.\nEnsure you have LSP Installed and its version is >= 2.0.0')

	# todo: get the actual window for the debugger session but good enough for now
	lsp = LspWindowCommand(sublime.active_window())
	lsp.session_name = session_name

	session = lsp.session()
	if not session:
		raise core.Error('There is no active `LSP-' + session_name + '` session which is required to start debugging')

	future = core.Future()
	session.send_request_async( # type: ignore
		Request(method, params),
		future.set_result,
		future.set_exception,
	)
	return await future
