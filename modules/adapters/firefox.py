from __future__ import annotations
from .. import dap
from . import util


class Firefox(dap.Adapter):
	type = 'firefox'
	docs = 'https://github.com/firefox-devtools/vscode-firefox-debug#getting-started'

	installer = util.GitInstaller(type='firefox', repo='daveleroy/vscode-firefox-debug')

	async def start(self, console: dap.Console, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, console)
		install_path = self.installer.install_path()
		command = [node, f'{install_path}/dist/adapter.bundle.js']
		return dap.StdioTransport(command)
