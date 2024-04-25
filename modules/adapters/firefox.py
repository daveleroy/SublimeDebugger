from __future__ import annotations

from .import util
from .. import dap
from .. import core

class Firefox(dap.AdapterConfiguration):

	type = 'firefox'
	docs = 'https://github.com/firefox-devtools/vscode-firefox-debug#getting-started'

	installer = util.GitInstaller(
		type='firefox',
		repo='daveleroy/vscode-firefox-debug'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)
		install_path = self.installer.install_path()
		command = [
			node,
			f'{install_path}/dist/adapter.bundle.js'
		]
		return dap.StdioTransport(command)
