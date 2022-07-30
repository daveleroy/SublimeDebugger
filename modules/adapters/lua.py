from __future__ import annotations
from ..typecheck import *

from .import util
from .. import dap
from .. import core
import shutil

class Lua(dap.AdapterConfiguration):

	type = 'lua-local'
	docs = 'https://github.com/tomblind/local-lua-debugger-vscode'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)

		install_path = util.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/extension/debugAdapter.js'
		]
		return dap.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = await util.openvsx.latest_release_vsix('tomblind','local-lua-debugger-vscode')
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

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		install_path = util.vscode.install_path(self.type)
		configuration['extensionPath'] = f'{install_path}/extension'
		return configuration 
