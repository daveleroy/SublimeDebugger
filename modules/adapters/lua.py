from __future__ import annotations
from . import util
from .. import dap


class Lua(dap.Adapter):
	type = 'lua-local'
	docs = 'https://github.com/tomblind/local-lua-debugger-vscode'

	installer = util.GitInstaller(type='lua-local', repo='daveleroy/local-lua-debugger-vscode')

	async def start(self, console: dap.Console, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, console)

		install_path = self.installer.install_path()
		command = [node, f'{install_path}/extension/debugAdapter.js']
		return dap.StdioTransport(command)

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		install_path = self.installer.install_path()
		configuration['extensionPath'] = f'{install_path}'
		return configuration
