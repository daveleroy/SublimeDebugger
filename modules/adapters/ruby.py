from ..typecheck import *
from ..import core
from .import adapter

import shutil

class Ruby(adapter.AdapterConfiguration):

	@property
	def type(self): return 'ruby'

	async def start(self, log, configuration):

		install_path = adapter.vscode.install_path(self.type)

		if not shutil.which("readapt"):
			raise core.Error('You must install the `readapt` gem. Install it by running `gem install readapt` see https://github.com/castwide/vscode-ruby-debug for details.')

		command = [
			'readapt',
			'stdio'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/castwide/vsextensions/ruby-debug/latest/vspackage'
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


