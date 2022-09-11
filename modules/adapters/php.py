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

	installer = util.GitInstaller (
		type='php',
		repo='xdebug/vscode-php-debug'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)

		install_path = util.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/phpDebug.js'
		]
		return dap.StdioTransport(log, command)
