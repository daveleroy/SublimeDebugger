from __future__ import annotations
from ..typecheck import *

from .import adapter
from .. import dap
from .. import core

import sublime
import re

class PHP(adapter.AdapterConfiguration):

	type = 'php'
	docs = 'https://github.com/xdebug/vscode-php-debug#installation'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await adapter.get_and_warn_require_node(self.type, log)

		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/phpDebug.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = 'https://github.com/xdebug/vscode-php-debug/releases/latest/download/php-debug.vsix'
		await adapter.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await adapter.git.installed_status('xdebug', 'vscode-php-debug', self.installed_version, log)

	@property
	def installed_version(self):
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return adapter.vscode.configuration_schema(self.type)

	def on_hover_provider(self, view: sublime.View, point: int):
		seperators = "./\\()\"'-:,.;<>~!@#%^&*|+=[]{}`~?."
		word = view.expand_by_class(point, sublime.CLASS_WORD_START | sublime.CLASS_WORD_END, separators=seperators)
		if not word:
			return None

		word_string = view.substr(word)
		match = re.search("\\$[a-zA-Z0-9_]*", word_string)
		if not match:
			return None

		word_string = match.group()
		return (match.group(), word)
