import shutil
from ...typecheck import *
from ..import adapter
from ..settings import Settings

import sublime

class Python(adapter.AdapterConfiguration):

	@property
	def type(self): return 'python'

	async def start(self, log, configuration):
		if configuration.request == "attach":
			connect = configuration.get("connect")
			if connect:
				host = connect.get("host", "localhost")
				port = connect.get("port")

				return adapter.SocketTransport(log, host, port)

			port = configuration.get("port")
			if port:
				host = configuration.get("host", "localhost")

				return adapter.SocketTransport(log, host, port)

			if not configuration.get("listen") and not configuration.get("processId"):
				sublime.error_message("Warning: Check your debugger configuration.\n\n'attach' requires 'connect', 'listen' or 'processId'.\n\nIf they contain a $variable that variable may not have existed.""")

		install_path = adapter.vscode.install_path(self.type)

		python = configuration.get("pythonPath")

		if not python:
			if shutil.which("python3"):
				python = "python3"
			else:
				python = "python"

		command = [
			python,
			f'{install_path}/extension/pythonFiles/lib/python/debugpy/adapter',
		]

		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/ms-python/vsextensions/python/latest/vspackage'
		await adapter.vscode.install(self.type, url, log)

	@property
	def installed_version(self) -> Optional[str]:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> Optional[list]:
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> Optional[dict]:
		return adapter.vscode.configuration_schema(self.type)

	# TODO: patch in env since python seems to not inherit it from the adapter proccess.
	async def configuration_resolve(self, configuration):
		if configuration.request == "launch":
			if not configuration.get("program"):
				sublime.error_message("Warning: Check your debugger configuration.\n\nField `program` in configuration is empty. If it contained a $variable that variable may not have existed.""")

		return configuration
