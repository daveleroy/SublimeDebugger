from ..typecheck import *
from .import adapter

class Chrome(adapter.AdapterConfiguration):

	type = 'chrome'
	docs = 'https://github.com/Microsoft/vscode-chrome-debug#using-the-debugger'

	async def start(self, log, configuration):
		node = await adapter.get_and_warn_require_node(self.type, log)
		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/src/chromeDebug.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = await adapter.openvsx.latest_release_vsix('msjsdiag', 'debugger-for-chrome')
		await adapter.vscode.install(self.type, url, log)

	async def installed_status(self, log):
		return await adapter.openvsx.installed_status('msjsdiag', 'debugger-for-chrome', self.installed_version)

	@property
	def installed_version(self) -> Optional[str]:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> Optional[list]:
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> Optional[dict]:
		return adapter.vscode.configuration_schema(self.type)

