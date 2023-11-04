from __future__ import annotations

from .import util
from .. import dap
from .. import core
from ..settings import Setting

import shutil
import os


class Go(dap.AdapterConfiguration):

	type = 'go'
	docs = 'https://github.com/golang/vscode-go/blob/master/docs/debugging.md#launch-configurations'

	installer = util.GitInstaller (
		type='go',
		repo='golang/vscode-go'
	)

	go_dlv = Setting['str|None'] (
		key='go_dlv',
		default=None,
		description='Sets a specific path for dlv if not set go will use whatever is in your path'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		port = util.get_open_port()
		dlv = self.go_dlv or shutil.which('dlv')
		if not dlv:
			raise core.Error('`dlv` not found see https://github.com/go-delve/delve for setting up delve')

		command = [
			dlv, 'dap', '--listen', f'localhost:{port}'
		]

		cwd = configuration.get('cwd')

		env = {}
		env.update(os.environ)
		env.update(configuration.get('env') or {})


		def stdout(data: str):
			# ignore this none program output line
			if data.startswith('DAP server listening at:'):
				return

			log('stdout', data)

		def stderr(data: str):
			log('stderr', data)

		return dap.SocketTransport(
			port=port,
			command=command,
			cwd=cwd,
			env=env,
			stderr=stderr,
			stdout=stdout
		)
