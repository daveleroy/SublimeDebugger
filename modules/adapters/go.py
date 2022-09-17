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

	installer = util.GitInstaller (
		type='go',
		repo='golang/vscode-go'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		port = util.get_open_port()
		dlv = Settings.go_dlv or shutil.which('dlv')
		if not dlv:
			raise core.Error('`dlv` not found see https://github.com/go-delve/delve for setting up delve')

		command = [
			dlv, 'dap', '--listen', f'localhost:{port}'
		]
		return await dap.SocketTransport.connect_with_process(log, command, port, process_is_program_output=True)
