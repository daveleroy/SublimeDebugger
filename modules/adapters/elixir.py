from __future__ import annotations
from ..typecheck import *

from .import adapter
from .. import dap
from .. import core

import shutil

class Elixir(adapter.AdapterConfiguration):

	type = "elixir"
	docs = "https://github.com/elixir-lsp/elixir-ls#debugger-support"

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):

		install_path = adapter.vscode.install_path(self.type)
		extension = 'bat' if core.platform.windows else 'sh'
		command = [
			f'{install_path}/extension/elixir-ls-release/debugger.{extension}'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log: core.Logger):

		url = await adapter.openvsx.latest_release_vsix("elixir-lsp", "elixir-ls")
		await adapter.vscode.install(self.type, url, log)

	@property
	def installed_version(self):
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return adapter.vscode.configuration_schema(self.type)


