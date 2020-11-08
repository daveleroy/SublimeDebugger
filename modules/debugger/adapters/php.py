# {
# 	"command": [
# 		"node",
# 		"${install_path}/extension/out/phpDebug.js"
# 	],
# 	"hover_word_regex_match" : "\\$[a-zA-Z0-9_]*",
# 	"hover_word_seperators" : "./\\()\"'-:,.;<>~!@#%^&*|+=[]{}`~?.",
# 	"dependencies": ["node"],
# 	"install": {
# 		"name": "vscode-php",
# 		"type": "vscode",
# 		"url": "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/felixfbecker/vsextensions/php-debug/latest/vspackage"
# 	}
# }

from ...typecheck import *
from ..import adapter

import sublime
import re

class PHP(adapter.AdapterConfiguration):
	@property
	def type(self):
		return 'php'

	async def start(self, log, configuration):
		node = await adapter.get_and_warn_require_node(self.type, log)

		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/phpDebug.js'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/felixfbecker/vsextensions/php-debug/latest/vspackage'
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

	def on_hover_provider(self, view, point):
		seperators = "./\\()\"'-:,.;<>~!@#%^&*|+=[]{}`~?."
		word = view.expand_by_class(point, sublime.CLASS_WORD_START | sublime.CLASS_WORD_END, separators=seperators)
		word_string = word and view.substr(word)
		if not word_string:
			return None

		match = re.search("\\$[a-zA-Z0-9_]*", word_string)
		if not match:
			return None

		word_string = match.group()
		return (match.group(), word)
