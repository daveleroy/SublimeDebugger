from __future__ import annotations
from . import util
from .. import dap
from .. import core
from .. import commands


class GDB(dap.Adapter):
	type = 'gdb'
	docs = 'https://github.com/WebFreak001/code-debug#debug'

	installer = util.GitInstaller(type='gdb', repo='WebFreak001/code-debug')

	async def start(self, console: dap.Console, configuration: dap.ConfigurationExpanded):
		node = await util.get_and_warn_require_node(self.type, console)
		install_path = self.installer.install_path()
		command = [node, f'{install_path}/out/src/gdb.js']
		return dap.StdioTransport(command)


class GDBAction(commands.Action):
	def enabled(self, debugger: dap.Debugger):
		return bool(debugger.session and debugger.session.is_paused and isinstance(debugger.session.adapter, GDB))


class GDBRecord(GDBAction):
	name = 'GDB: Start recording for reverse debugging'
	key = 'gdb_record'

	@core.run
	async def action(self, debugger: dap.Debugger):
		try:
			await debugger.current_session.request('evaluate', {'expression': 'record'})
		except core.Error as e:
			debugger.console.error(f'Unable to start recording: {e}')


class GDBStepBackOver(GDBAction):
	name = 'GDB: Step Back Over'
	key = 'gdb_reverse_next'

	@core.run
	async def action(self, debugger: dap.Debugger):
		try:
			await debugger.current_session.request('evaluate', {'expression': 'reverse-next'})
		except core.Error as e:
			debugger.console.error(f'Unable to reverse-next: {e}')


class GDBStepBackOut(GDBAction):
	name = 'GDB: Step Back Out'
	key = 'gdb_reverse_finish'

	@core.run
	async def action(self, debugger: dap.Debugger):
		try:
			await debugger.current_session.request('evaluate', {'expression': 'reverse-finish'})
		except core.Error as e:
			debugger.console.error(f'Unable to reverse-finish: {e}')
