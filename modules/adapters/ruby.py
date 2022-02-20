from __future__ import annotations
from ..typecheck import *

from .import util
from .. import dap
from .. import core

import shutil

class Ruby(dap.AdapterConfiguration):

	type = 'ruby'
	docs = 'https://github.com/castwide/vscode-ruby-debug#debugging-external-programs'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):

		install_path = util.vscode.install_path(self.type)

		if not shutil.which("readapt"):
			raise core.Error('You must install the `readapt` gem. Install it by running `gem install readapt` see https://github.com/castwide/vscode-ruby-debug for details.')

		command = [
			'readapt',
			'stdio'
		]
		return dap.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = await util.openvsx.latest_release_vsix('wingrunr21', 'vscode-ruby')
		await util.vscode.install(self.type, url, log)

	@property
	def installed_version(self):
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema(self.type)


