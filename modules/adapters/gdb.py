from __future__ import annotations

from .import util
from .. import dap
from .. import core
from .. import commands


class GDB(dap.AdapterConfiguration):

	type = 'gdb'
	docs = 'https://github.com/WebFreak001/code-debug#debug'

	installer = util.GitInstaller(
		type='gdb',
		repo='WebFreak001/code-debug'
	)

	def __init__(self) -> None:

		commands.Command (
			name='GDB: Start recording for reverse debugging',
			key='gdb_record',
			action=lambda debugger: self.record(debugger),
			enabled=self.gdb_commmands_enabled
		)
		commands.Command (
			name='GDB: Step Back Over',
			key='gdb_reverse_next',
			action=lambda debugger: self.reverse_next(debugger),
			enabled=self.gdb_commmands_enabled
		)
		commands.Command (
			name='GDB: Step Back Out',
			key='gdb_reverse_finish',
			action=lambda debugger: self.reverse_finish(debugger),
			enabled=self.gdb_commmands_enabled
		)

	def gdb_commmands_enabled(self, debugger: dap.Debugger):
		return bool(debugger.session and debugger.session.is_paused and debugger.session.adapter_configuration is self)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, log)
		install_path = self.installer.install_path()
		command = [
			node,
			f'{install_path}/out/src/gdb.js'
		]
		return dap.StdioTransport(command)

	@core.run
	async def record(self, debugger: dap.Debugger) -> None:
		try:
			await debugger.current_session.request('evaluate', {'expression': 'record'})
		except core.Error as e:
			debugger.console.error(f'Unable to start recording: {e}')

	@core.run
	async def reverse_next(self, debugger: dap.Debugger) -> None:
		try:
			await debugger.current_session.request('evaluate', {'expression': 'reverse-next'})
		except core.Error as e:
			debugger.console.error(f'Unable to reverse-next: {e}')

	@core.run
	async def reverse_finish(self, debugger: dap.Debugger) -> None:
		try:
			await debugger.current_session.request('evaluate', {'expression': 'reverse-finish'})
		except core.Error as e:
			debugger.console.error(f'Unable to reverse-finish: {e}')
