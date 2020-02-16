from ...typecheck import *
from ..import adapter

class Firefox(adapter.Adapter):
	@property
	def type(self): 
		return 'firefox'

	async def start(self, log):
		install_path = adapter.vscode.install_path(self.type)
		command = [
			f'node',
			f'{install_path}/extension/out/adapter/firefoxDebugAdapter.js'
		]
		return adapter.ProcessTransport(command, log)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/firefox-devtools/vsextensions/vscode-firefox-debug/latest/vspackage'
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