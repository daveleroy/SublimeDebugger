
from sublime_db import core

from .debugger import DebugAdapterClient, DebuggerState, Variable
from .components.console_panel import ConsolePanel

@core.async
def run_repl_command(command: str, debugger: DebuggerState, console: ConsolePanel) -> core.awaitable[None]:
	console.Add(command)

	adapter = debugger.adapter

	if not adapter:
		console.AddStderr(str("Failed to run command: Debugger is not running"))
		return

	try:
		response = yield from adapter.Evaluate(command, debugger.frame, "repl")
	except Exception as e:
		console.AddStderr(str(e))
		return

	if response.variablesReference:
		variable = Variable(adapter, response.result, '', response.variablesReference)
		console.AddVariable(variable)
	else:
		console.AddStdout(response.result)

