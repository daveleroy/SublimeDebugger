from ...typecheck import *
from ..import adapter
from ...import core

class LLDB(adapter.Adapter):
	@property
	def type(self): 
		return "lldb"

	async def start(self, log: core.Logger):
		install_path = adapter.vscode.install_path(self.type)
		command = [
			f'node',
			f'{core.current_package()}/debug_adapters/lldb_util/entry.js',
			f'{install_path}/extension/adapter2/codelldb'
		]
		return adapter.ProcessTransport(command, log)

	async def install(self, log: core.Logger):
		if core.platform.windows:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/vscode-lldb-x86_64-windows.vsix'
		if core.platform.osx:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/vscode-lldb-x86_64-darwin.vsix'
		if core.platform.linux:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/vscode-lldb-x86_64-linux.vsix'

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
