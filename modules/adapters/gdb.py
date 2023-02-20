from __future__ import annotations

from .import util
from .. import dap
from .. import core

class GDB(dap.AdapterConfiguration):
	
	type = 'gdb'
	docs = 'https://github.com/WebFreak001/code-debug#debug'

	installer = util.GitInstaller(
		type='gdb',
		repo='WebFreak001/code-debug'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)
		install_path = self.installer.install_path()
		command = [
			node,
			f'{install_path}/extension/out/src/gdb.js'
		]
		return dap.StdioTransport(log, command)
