from __future__ import annotations
from . import util
from .. import dap


class PHP(dap.Adapter):
	type = 'php'
	docs = 'https://github.com/xdebug/vscode-php-debug#installation'

	installer = util.GitInstaller(type='php', repo='xdebug/vscode-php-debug')

	async def start(self, console: dap.Console, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, console)

		install_path = self.installer.install_path()
		command = [node, f'{install_path}/out/phpDebug.js']
		return dap.StdioTransport(command)
