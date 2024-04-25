from __future__ import annotations

from .import util
from .. import dap
from .. import core

import os

class MockInstaller(util.vscode.AdapterInstaller):
	type = 'mock'

	async def install(self, version: str|None, log: core.Logger):
		url = 'https://codeload.github.com/microsoft/vscode-mock-debug/zip/refs/heads/main'
		await self.install_source(url, log=log)

	async def post_install(self, version: str|None, log: core.Logger):
		install_path = self.temporary_install_path()

		log.info('building mock debug adapter')
		log.info('npm install')
		await dap.Process.check_output(['npm', 'install'], cwd=install_path)
		log.info('npm run compile')
		await dap.Process.check_output(['npm', 'run', 'compile'], cwd=install_path)

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
			f'{install_path}/out/debugAdapter.js'
		]
		return dap.StdioTransport(command)
