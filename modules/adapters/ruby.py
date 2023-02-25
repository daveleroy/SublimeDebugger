from __future__ import annotations

from .import util
from .. import dap
from .. import core
import shutil


class Ruby(dap.AdapterConfiguration):

	type = 'rdbg'
	types = ['ruby', 'ruby-debug']

	docs = 'https://github.com/ruby/vscode-rdbg#how-to-use'

	installer = util.git.GitSourceInstaller (
		type='rdbg',
		repo='ruby/vscode-rdbg',
	)


	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		rdbg = shutil.which('rdbg')
		if not rdbg:
			raise core.Error('You must install the `rdbg` gem. Install it by running `gem install rdbg`')

		port = util.get_open_port()
		command = [
			rdbg,
			"--open", "--host", "localhost", "--port", f'{port}', '-c', '--',
		]

		configuration['command'] = configuration.get('command') or 'ruby'

		script = configuration['script']

		if configuration.get('useBundler'):
			command.extend(["bundle", "exec", configuration['command'], script])
		else:
			command.extend([configuration['command'], script])

		transport = await dap.SocketTransport.connect_with_process(log, command, port, process_is_program_output=True)
		assert transport.process

		def stdout(data: str):
			log.log('stdout',data)

		def stderr(data: str):
			hidden = data.startswith('DEBUGGER: ')
			if hidden:
				log.log('transport', dap.TransportStderrOutputLog(data))
			else:
				log.log('stderr',data)

		transport.process.on_stdout(stdout)
		transport.process.on_stderr(stderr)
		return transport


