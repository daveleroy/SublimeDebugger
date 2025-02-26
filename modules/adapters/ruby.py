from __future__ import annotations

from . import util
from .. import dap
from .. import core
import shutil


class Ruby(dap.Adapter):
	type = ['rdbg', 'ruby', 'ruby-debug']

	docs = 'https://github.com/ruby/vscode-rdbg#how-to-use'

	installer = util.git.GitSourceInstaller(
		type='rdbg',
		repo='ruby/vscode-rdbg',
	)

	async def start(self, console: dap.Console, configuration: dap.ConfigurationExpanded):
		rdbg = shutil.which('rdbg')
		if not rdbg:
			raise core.Error('You must install the `rdbg` gem. Install it by running `gem install rdbg`')

		port = util.get_open_port()
		command = [
			rdbg,
			'--open',
			'--host',
			'localhost',
			'--port',
			f'{port}',
			'-c',
			'--',
		]

		configuration['command'] = configuration.get('command') or 'ruby'

		script = configuration['script']

		if configuration.get('useBundler'):
			command.extend(['bundle', 'exec', configuration['command'], script])
		else:
			command.extend([configuration['command'], script])

		def stdout(data: str):
			console.log('stdout', data)

		def stderr(data: str):
			hidden = data.startswith('DEBUGGER: ')
			if hidden:
				console.log('transport', dap.TransportOutputLog('stderr', data))
			else:
				console.log('stderr', data)

		return dap.SocketTransport(port=port, command=command, stdout=stdout, stderr=stderr)
