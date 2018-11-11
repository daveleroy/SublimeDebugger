
import sublime
import sublime_plugin

from sublime_db import core
from sublime_db import ui
from sublime_db.libs import asyncio

from .debugger import DebugAdapterClient, DebuggerState, Variable
from .debug_adapter_client.types import CompletionItem
from .components.console_panel import ConsolePanel

# FIXME This wont work for multiple windows with multiple repl commands running...

@core.async
def run_repl_command(command: str, debugger: DebuggerState, console: ConsolePanel) -> core.awaitable[None]:
	console.Add(command)

	adapter = debugger.adapter

	if not adapter:
		console.AddStderr(str("Failed to run command: Debugger is not running"))
		return

	try:
		response = yield from adapter.Evaluate(command, "repl")
	except Exception as e:
		console.AddStderr(str(e))
		return

	if response.variablesReference:
		variable = Variable(adapter, response.result, '', response.variablesReference)
		console.AddVariable(variable)
	else:
		console.AddStdout(response.result)

