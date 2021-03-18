from __future__ import annotations
from ..typecheck import *

from .import adapter
from .. import dap
from .. import core

import shutil

class Ruby(adapter.AdapterConfiguration):

	type = 'ruby'
	docs = 'https://github.com/castwide/vscode-ruby-debug#debugging-external-programs'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):

		install_path = adapter.vscode.install_path(self.type)

		if not shutil.which("readapt"):
			raise core.Error('You must install the `readapt` gem. Install it by running `gem install readapt` see https://github.com/castwide/vscode-ruby-debug for details.')

		command = [
			'readapt',
			'stdio'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = await adapter.openvsx.latest_release_vsix('wingrunr21', 'vscode-ruby')
		await adapter.vscode.install(self.type, url, log)

	@property
	def installed_version(self):
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return adapter.vscode.configuration_schema(self.type)


