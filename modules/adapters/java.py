# Basic idea here is...
# When installing the adapter it would add the com.microsoft.java.debug.plugin-0.30.0.jar as a plugin to lsp-jdts
# When starting the adapter it will ask lsp-jdts to start the adapter by calling the command lsp_jdts_start_debugging exposed by lsp-jdts
# lsp-jdts will then call debugger_lsp_jdts_start_debugging_response after it has started the adapter
# Debugger will then connect to the given port and start debugging

# see https://github.com/Microsoft/java-debug for how the lsp side needs to be setup
# command to start the debug session
#   {
#       "command": "vscode.java.startDebugSession"
#   }

from ..typecheck import Optional, Dict
from ..import core
from ..import dap
from .import util

import sublime
import sublime_plugin
import os


class DebuggerLspJdtlsStartDebuggingResponseCommand(sublime_plugin.WindowCommand):
	# window.run_command('debugger_lsp_jdtls_start_debugging_response', {'id': 1, 'port': 12345, 'error': None})

	def run(self, **args):
		future = Java.pending_adapters.get(args["id"])
		if not future:
			print("Hmm... unable to find a future port for this id")
			return

		future.set_result(args)


class Java(dap.AdapterConfiguration):
	pending_adapters: Dict[int, core.Future] = {}
	pending_adapters_current_id = 0

	type = "java"
	docs = "https://github.com/redhat-developer/vscode-java/blob/master/README.md"

	async def start(self, log, configuration):
		pc_settings = sublime.load_settings("Package Control.sublime-settings")
		installed_packages = pc_settings.get("installed_packages", [])

		if "LSP-jdtls" not in installed_packages or "LSP" not in installed_packages:
			raise core.Error("LSP and LSP-jdtls required to debug Java!")

		# probably need to add some sort of timeout
		future = core.Future()

		id = Java.pending_adapters_current_id
		Java.pending_adapters_current_id += 1
		Java.pending_adapters[id] = future

		# ask lsp_jdts to start the debug adapter
		# lsp_jdts will call debugger_lsp_jdts_start_debugging_response with the id it was given and a port to connect to the adapter with or an error
		# note: the active window might not match the debugger window but generally will... probably need a way to get the actual window.
		sublime.active_window().run_command("lsp_jdtls_start_debug_session", {"id": id})

		args = await future
		if "cwd" not in configuration:
			configuration["cwd"], _ = os.path.split(
				sublime.active_window().project_file_name()
			)
		if "mainClass" not in configuration or not configuration["mainClass"]:
			if "mainClass" not in args:
				raise core.Error(args["error"])
			configuration["mainClass"] = args["mainClass"]
		if "classPaths" not in configuration:
			if "classPaths" not in args:
				raise core.Error(args["error"])
			configuration["classPaths"] = args["classPaths"]
		if "modulePaths" not in configuration:
			configuration["modulePaths"] = args["modulePaths"]
		if "console" not in configuration:
			configuration["console"] = "internalConsole"
		if args["enablePreview"]:
			if "vmArgs" in configuration:
				configuration["vmArgs"] += " --enable-preview"
			else:
				configuration["vmArgs"] = "--enable-preview"

		return dap.SocketTransport(log, "localhost", args["port"])

	async def install(self, log):
		url = await util.openvsx.latest_release_vsix("vscjava", "vscode-java-debug")
		await util.vscode.install(self.type, url, log)

	async def installed_status(self, log):
		return await util.openvsx.installed_status(
			"vscjava", "vscode-java-debug", self.installed_version
		)

	@property
	def installed_version(self) -> Optional[str]:
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> Optional[list]:
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> Optional[dict]:
		return util.vscode.configuration_schema(self.type)
