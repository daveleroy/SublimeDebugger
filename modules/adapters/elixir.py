from __future__ import annotations
import os
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
		paths = [
			f'{install_path}/elixir-ls-release/debug_adapter.{extension}',
			f'{install_path}/elixir-ls-release/debugger.{extension}',
		]
		for path in paths:
			if os.path.exists(path):
				return dap.StdioTransport([path], stderr=console.error)

		raise dap.Error(f'Unable to find elixir debugger searched {paths}')
