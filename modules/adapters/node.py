from __future__ import annotations
from ..typecheck import *

from .import util
from .. import dap
from .. import core

class NodeLegacy(dap.AdapterConfiguration):

	type = 'node-legacy'
	docs = 'https://github.com/microsoft/vscode-docs/blob/main/docs/nodejs/nodejs-debugging.md#nodejs-debugging-in-vs-code'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)
		install_path = util.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/src/nodeDebug.js'
		]
		return dap.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = await util.openvsx.latest_release_vsix('ms-vscode', 'node-debug2')
		await util.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await util.openvsx.installed_status('ms-vscode', 'node-debug2', self.installed_version, log)

	@property
	def installed_version(self):
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets(self.type, 'legacy-node2')

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema(self.type, 'legacy-node2')
