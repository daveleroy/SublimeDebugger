from __future__ import annotations
from .. import dap
from .. import core
from . import util


class Elixir(dap.Adapter):
	type = ['elixir', 'mix_task']

	docs = 'https://github.com/elixir-lsp/elixir-ls#debugger-support'

	installer = util.GitInstaller(type='elixir', repo='daveleroy/vscode-elixir-ls')

	async def start(self, console: dap.Console, configuration: dap.ConfigurationExpanded):
		install_path = self.installer.install_path()
		extension = 'bat' if core.platform.windows else 'sh'
		command = [f'{install_path}/elixir-ls-release/debugger.{extension}']
		return dap.StdioTransport(command, stderr=console.error)
