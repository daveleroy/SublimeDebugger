from __future__ import annotations

from .import util
from .. import dap
from .. import core

import os

class MockInstaller(util.vscode.AdapterInstaller):
	type = 'mock'

	async def install(self, version: str|None, log: core.Logger):
		url = 'https://codeload.github.com/microsoft/vscode-mock-debug/zip/refs/heads/main'

		async def post_download_action():
			install_path = self.install_path()
			extension_folder = os.path.join(install_path, 'extension')

			log.info('building mock debug adapter')
			log.info('npm install')
			await dap.Process.check_output(['npm', 'install'], cwd=extension_folder)
			log.info('npm run compile')
			await dap.Process.check_output(['npm', 'run', 'compile'], cwd=extension_folder)

		await self.install_from_asset(url, log, post_download_action)
	
	async def installable_versions(self, log: core.Logger):
		return ['head']

class Mock(dap.AdapterConfiguration):

	type = 'mock'
	docs = 'https://github.com/microsoft/vscode-mock-debug#vs-code-mock-debug'
	development = True
	installer = MockInstaller()

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)
		install_path = self.installer.install_path()
		command = [
			node,
			f'{install_path}/extension/out/debugAdapter.js'
		]
		return dap.StdioTransport(log, command)


