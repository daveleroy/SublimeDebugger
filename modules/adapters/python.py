from __future__ import annotations
from ..typecheck import *

from ..settings import Settings
from .import adapter
from .. import dap
from .. import core

import sublime
import shutil

class Python(adapter.AdapterConfiguration):

	type = 'python'
	docs = 'https://github.com/microsoft/vscode-docs/blob/main/docs/python/debugging.md#python-debug-configurations-in-visual-studio-code'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
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
				sublime.error_message("Warning: Check your debugger configuration.\n\n'attach' requires 'connect', 'listen' or 'processId'.\n\nIf they contain a $variable that variable may not have existed.")

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

	async def install(self, log: core.Logger):
		url = await adapter.git.latest_release_vsix('microsoft', 'vscode-python')
		await adapter.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await adapter.git.installed_status('microsoft', 'vscode-python', self.installed_version, log)

	@property
	def installed_version(self) -> str|None:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return adapter.vscode.configuration_schema(self.type)

	# TODO: patch in env since python seems to not inherit it from the adapter proccess.
	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		if configuration.request == "launch":
			if not configuration.get("program") and not configuration.get("module"):
				sublime.error_message("Warning: Check your debugger configuration.\n\nBold fields `program` and `module` in configuration are empty. If they contained a $variable that variable may not have existed.")

		return configuration
