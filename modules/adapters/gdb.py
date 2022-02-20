from __future__ import annotations
from ..typecheck import *

from .import util
from .. import dap
from .. import core

class GDB(dap.AdapterConfiguration):
	
	type = 'gdb'
	docs = 'https://github.com/WebFreak001/code-debug#debug'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)
		install_path = util.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/src/gdb.js'
		]
		return dap.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = await util.openvsx.latest_release_vsix('webfreak', 'debug')
		await util.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await util.openvsx.installed_status('webfreak', 'debug', self.installed_version, log)

	@property
	def installed_version(self):
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema(self.type)
