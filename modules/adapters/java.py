# Basic idea here is...
# When installing the adapter it would add the com.microsoft.java.debug.plugin-0.30.0.jar as a plugin to lsp-jdts
# When starting the adapter it will ask lsp-jdts to start the adapter by calling the command lsp_jdts_start_debugging exposed by lsp-jdts
# lsp-jdts will then call debugger_lsp_jdts_start_debugging_response after it has started the adapter
# Debugger will then connect to the given port and start debugging

# see https://github.com/Microsoft/java-debug for how the lsp side needs to be setup it looks something like....
# add the jar to the init options
#	"initializationOptions": {
#		"bundles": [
#			"path/to/microsoft/java-debug/com.microsoft.java.debug.plugin/target/com.microsoft.java.debug.plugin-<version>.jar"
#		]
#	}
# command to start the debug session
# 	{
#		"command": "vscode.java.startDebugSession"
# 	}

from ..typecheck import *
from .. import core
from .import adapter

import sublime
import sublime_plugin

# window.run_command('debugger_lsp_jdts_start_debugging_response', {'id': 1, 'port': 12345, 'error': None})
class DebuggerLspJdtsStartDebuggingResponseCommand(sublime_plugin.WindowCommand):
	def run(self, id: int, port: Optional[int], error: Optional[str]):
		future_port = Java.pending_adapters.get(id)
		if not future_port:
			print("Hmm... unable to find a future port for this id")
			return

		if error:
			future_port.set_exception(core.Error(error))
			return

		if not port:
			future_port.set_exception(core.Error('Expected port or error from lsp-jdts'))
			return

		future_port.set_result(port)			


class Java(adapter.AdapterConfiguration):
	pending_adapters: Dict[int, core.future] = {}
	pending_adapters_current_id = 0

	@property
	def type(self): return 'java'

	async def start(self, log, configuration):
		# probably need to add some sort of timeout
		# probably need to ensure lsp_jdts is installed
		# probably need to ensure lsp_jdts has the plugin jar patched in
		future_port = core.create_future()

		id = Java.pending_adapters_current_id
		Java.pending_adapters_current_id += 1
		Java.pending_adapters[id] = future_port

		# ask lsp_jdts to start the debug adapter
		# lsp_jdts will call debugger_lsp_jdts_start_debugging_response with the id it was given and a port to connect to the adapter with or an error
		# note: the active window might not match the debugger window but generally will... probably need a way to get the actual window.
		sublime.active_window().run_command('lsp_jdts_start_debugging', {
			'id': id
		})

		port = await future_port
		return adapter.SocketTransport(log, 'localhost', port)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/vscjava/vsextensions/vscode-java-debug/latest/vspackage'
		await adapter.vscode.install(self.type, url, log)

		install_path = adapter.vscode.install_path(self.type)

		# probably need to just look through this folder? this has a version #
		plugin_jar_path = f'{install_path}/extension/server/com.microsoft.java.debug.plugin-0.30.0.jar'
		
		# TODO patch in the jar to lsp-jdts
		# TODO restart lsp-jdts?
		# probably need to allow running some stuff after downloading the extension but before it is marked as installed because this patching needs to succeed

	@property
	def installed_version(self) -> Optional[str]:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> Optional[list]:
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> Optional[dict]:
		return adapter.vscode.configuration_schema(self.type)

