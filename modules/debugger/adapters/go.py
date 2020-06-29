from ...typecheck import *
from ..import adapter

from ..util import get_debugger_setting

import shutil

class Go(adapter.Adapter):
	@property
	def type(self):
		return "go"

	async def start(self, log, configuration):
		node = adapter.get_and_warn_require_node(self.type, log)
		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/src/debugAdapter/goDebug.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/golang/vsextensions/Go/latest/vspackage'
		await adapter.vscode.install(self.type, url, log)

	# Patch in dlvToolPath to point to dlv if present in settings or path
	# TODO: Implement more of the functionality in
	# https://github.com/microsoft/vscode-go/blob/master/src/goDebugConfiguration.ts
	def configuration_resolve(self, configuration):
		if not 'dlvToolPath' in configuration:
			configuration['dlvToolPath'] = get_debugger_setting('go.dlv') or shutil.which('dlv')

		return configuration

	@property
	def installed_version(self) -> Optional[str]:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> list:
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> dict:
		return adapter.vscode.configuration_schema(self.type)
