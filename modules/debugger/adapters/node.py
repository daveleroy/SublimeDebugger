from ...typecheck import *
from ..import adapter

class Node(adapter.Adapter):

	@property
	def type(self): return 'node'

	@property
	def info(self): return adapter.vscode.info(self.type)

	async def start(self, log, configuration):
		node = adapter.get_and_warn_require_node(self.type, log)
		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/src/nodeDebug.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/ms-vscode/vsextensions/node-debug2/latest/vspackage'
		await adapter.vscode.install(self.type, url, log)

	@property
	def installed_version(self) -> Optional[str]:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> list:
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> dict:
		return adapter.vscode.configuration_schema(self.type)
