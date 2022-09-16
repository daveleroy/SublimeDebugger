from __future__ import annotations
from ..typecheck import *

from .. import dap
from .. import core
from . import util
import shutil

class Elixir(dap.AdapterConfiguration):

	type = 'elixir'
	types = ['exiter', 'mix_task']

	docs = 'https://github.com/elixir-lsp/elixir-ls#debugger-support'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):

		install_path = util.vscode.install_path(self.type)
		extension = 'bat' if core.platform.windows else 'sh'
		command = [
			f'{install_path}/extension/elixir-ls-release/debugger.{extension}'
		]
		return dap.StdioTransport(log, command, stderr=log.error)

	async def install(self, log: core.Logger):

		url = await util.openvsx.latest_release_vsix("elixir-lsp", "elixir-ls")
		await util.vscode.install(self.type, url, log)

	@property
	def installed_version(self):
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema(self.type)


