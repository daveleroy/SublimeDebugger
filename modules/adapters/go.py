from __future__ import annotations
from ..typecheck import *

from ..settings import Settings

from .import util
from .. import dap
from .. import core

import shutil


class Go(dap.AdapterConfiguration):

	type = 'go'
	docs = 'https://github.com/golang/vscode-go/blob/master/docs/debugging.md#launch-configurations'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		port = util.get_open_port()
		dlv = Settings.go_dlv or shutil.which('dlv')
		if not dlv:
			raise core.Error('`dlv` not found see https://github.com/go-delve/delve for setting up delve')

		command = [
			dlv, 'dap', '--listen', f'localhost:{port}'
		]
		return await dap.SocketTransport.connect_with_process(log, command, port, process_is_program_output=True)
		
	async def install(self, log: core.Logger):
		url = await util.git.latest_release_vsix('golang', 'vscode-go')
		await util.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await util.git.installed_status('golang', 'vscode-go', self.installed_version, log)

	@property
	def installed_version(self) -> str|None:
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema(self.type)
