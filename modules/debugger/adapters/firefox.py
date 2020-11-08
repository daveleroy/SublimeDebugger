from ...typecheck import *
from ..import adapter

class Firefox(adapter.AdapterConfiguration):
	@property
	def type(self):
		return 'firefox'

	async def start(self, log, configuration):
		node = await adapter.get_and_warn_require_node(self.type, log)
		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/dist/adapter.bundle.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/firefox-devtools/vsextensions/vscode-firefox-debug/latest/vspackage'
		await adapter.vscode.install(self.type, url, log)

	@property
	def installed_version(self) -> Optional[str]:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> Optional[list]:
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> Optional[dict]:
		return adapter.vscode.configuration_schema(self.type)
