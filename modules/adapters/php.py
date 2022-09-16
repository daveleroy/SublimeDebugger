from __future__ import annotations
from ..typecheck import *

from .import util
from .. import dap
from .. import core

import sublime
import re

class PHP(dap.AdapterConfiguration):

	type = 'php'
	docs = 'https://github.com/xdebug/vscode-php-debug#installation'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)

		install_path = util.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/phpDebug.js'
		]
		return dap.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = await util.git.latest_release_vsix('xdebug', 'vscode-php-debug')
		await util.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await util.git.installed_status('xdebug', 'vscode-php-debug', self.installed_version, log)

	@property
	def installed_version(self):
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema(self.type)
