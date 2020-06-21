from ...typecheck import *
from ..import adapter
from ...import core
from ..adapter.transports import CommandSocketTransport
from ..util import get_debugger_setting

import subprocess
class LLDB(adapter.Adapter):
	@property
	def type(self):
		return "lldb"

	async def start(self, log: core.Logger, configuration):
		install_path = adapter.vscode.install_path(self.type)

		codelldb = f'{install_path}/extension/adapter2/codelldb'
		libpython = subprocess.check_output([codelldb, "find-python"]).strip()
		command = [
			codelldb,
			"--libpython", libpython
		]
		return CommandSocketTransport(log, command)

	async def install(self, log: core.Logger):
		if core.platform.windows:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-windows.vsix'
		if core.platform.osx:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-darwin.vsix'
		if core.platform.linux:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-linux.vsix'

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
