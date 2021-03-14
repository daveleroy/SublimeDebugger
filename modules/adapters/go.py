from ..typecheck import *
from ..settings import Settings

from .import adapter

import shutil

class Go(adapter.AdapterConfiguration):

	type = 'go'
	docs = 'https://github.com/golang/vscode-go/blob/master/docs/debugging.md#launch-configurations'

	async def start(self, log, configuration):
		node = await adapter.get_and_warn_require_node(self.type, log)
		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/dist/debugAdapter.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = await adapter.git.latest_release_vsix('golang', 'vscode-go')
		await adapter.vscode.install(self.type, url, log)

	async def installed_status(self, log):
		return await adapter.git.installed_status('golang', 'vscode-go', self.installed_version)

	@property
	def installed_version(self) -> Optional[str]:
		return adapter.vscode.installed_version(self.type)

	# Patch in dlvToolPath to point to dlv if present in settings or path
	# TODO: Implement more of the functionality in
	# https://github.com/microsoft/vscode-go/blob/master/src/goDebugConfiguration.ts
	async def configuration_resolve(self, configuration):
		if not 'dlvToolPath' in configuration:
			configuration['dlvToolPath'] = Settings.go_dlv or shutil.which('dlv')

		return configuration


	@property
	def configuration_snippets(self) -> Optional[list]:
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> Optional[dict]:
		return adapter.vscode.configuration_schema(self.type)
