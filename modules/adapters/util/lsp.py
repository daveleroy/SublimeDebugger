from typing import Any

from ... import core
from .bridge import DebuggerBridgeCommand, TimedOut

async def request(session_name: str, method: str, params: Any) -> Any:
	try:
		return await DebuggerBridgeCommand.request('debugger_bridge_lsp_request', session_name=session_name, method=method, params=params)
	except TimedOut:
		raise core.Error('Unable to connect to LSP client (timed out)') from None
