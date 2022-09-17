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

	installer = util.OpenVsxInstaller(
		type='elixir', 
		repo='elixir-lsp/elixir-ls'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):

		install_path = util.vscode.install_path(self.type)
		extension = 'bat' if core.platform.windows else 'sh'
		command = [
			f'{install_path}/extension/elixir-ls-release/debugger.{extension}'
		]
		return dap.StdioTransport(log, command, stderr=log.error)
