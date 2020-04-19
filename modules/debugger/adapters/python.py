from ...typecheck import *
from ..import adapter

class Python(adapter.Adapter):

	@property
	def type(self): return 'python'

	async def start(self, log):
		node = adapter.get_and_warn_require_node_less_than_or_equal(self.type, log, 'v12.5.0')
		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/client/debugger/debugAdapter/main.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/ms-python/vsextensions/python/latest/vspackage'
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
