from __future__ import annotations
from ..typecheck import *

from .import adapter
from .. import dap
from .. import core

class Node(adapter.AdapterConfiguration):

	type = 'node'
	docs = 'https://github.com/microsoft/vscode-docs/blob/main/docs/nodejs/nodejs-debugging.md#nodejs-debugging-in-vs-code'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await adapter.get_and_warn_require_node(self.type, log)
		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/src/nodeDebug.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = await adapter.openvsx.latest_release_vsix('ms-vscode', 'node-debug2')
		await adapter.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await adapter.openvsx.installed_status('ms-vscode', 'node-debug2', self.installed_version, log)

	@property
	def installed_version(self):
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return adapter.vscode.configuration_snippets(self.type, 'node2')

	@property
	def configuration_schema(self):
		return adapter.vscode.configuration_schema(self.type, 'node2')
