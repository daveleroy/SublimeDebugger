from __future__ import annotations
from typing import Any

import sublime
from ... import dap
from ... import core

async def request(session_names: str | tuple[str, ...], method: str, params: Any) -> Any:
	"""
	Sends a request to the first active LSP session matching one of the given session names.
	"""
	if isinstance(session_names, str):
		session_names = (session_names,)

	try:
		from LSP.plugin import Request, LspWindowCommand
	except ImportError:
		raise dap.Error('This debug adapter requires LSP which does not appear to be installed.\nEnsure you have LSP Installed and its version is >= 2.0.0')

	# todo: get the actual window for the debugger session but good enough for now
	lsp = LspWindowCommand(sublime.active_window())

	session = None
	for session_name in session_names:
		lsp.session_name = session_name
		session = lsp.session()
		if session:
			break

	if not session:
		raise dap.Error(f'There is no active `{session_names[0]}` session which is required to start debugging')

	future = core.Future()
	session.send_request_async( # type: ignore
		Request(method, params),
		future.set_result,
		future.set_exception,
	)
	return await future
