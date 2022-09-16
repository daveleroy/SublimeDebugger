from __future__ import annotations
from ..typecheck import *

from .import util
from .. import dap
from .. import core

import os

class Mock(dap.AdapterConfiguration):

	type = 'mock'
	docs = 'https://github.com/microsoft/vscode-mock-debug#vs-code-mock-debug'
	development = True

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)
		install_path = util.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/debugAdapter.js'
		]
		return dap.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = 'https://codeload.github.com/microsoft/vscode-mock-debug/zip/refs/heads/main'

		async def post_download_action():
			install_path = util.vscode.install_path(self.type)
			
			original_folder = os.path.join(install_path, 'vscode-mock-debug-main')
			extension_folder = os.path.join(install_path, 'extension')
			
			# rename the folder so it matches the vscode convention
			# since the util.vscode code assumes this
			os.rename(original_folder, extension_folder)

			log.info('building mock debug adapter')
			log.info('npm install')
			await dap.Process.check_output(['npm', 'install'], cwd=extension_folder)
			log.info('npm run compile')
			await dap.Process.check_output(['npm', 'run', 'compile'], cwd=extension_folder)

		await util.vscode.install(self.type, url, log, post_download_action)
		

	@property
	def installed_version(self):
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema(self.type)
