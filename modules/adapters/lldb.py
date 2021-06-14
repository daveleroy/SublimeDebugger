from __future__ import annotations
from ..typecheck import *

from ..import core
from ..import ui

from ..debugger import dap
from ..settings import Settings
from ..views.input_list_view import InputListView
from ..import commands

from .import adapter

import subprocess
import re
import threading
import sublime


class LLDBTransport(adapter.SocketTransport):
	def __init__(self, adapter_process: adapter.Process, port: int, log: core.Logger):
		self.process = adapter_process

		super().__init__(log, 'localhost', port)

		thread = threading.Thread(target=self._read, args=(self.process.stderr, lambda line: log.log('process', line)))
		thread.start()

	def _read(self, file: Any, callback: Callable[[str], None]) -> None:
		while True:
			try:
				line = file.read(2**15).decode('UTF-8')
				if not line:
					core.log_info("Nothing to read from process, closing")
					break
				core.log_info(line)
				core.call_soon_threadsafe(callback, line)
			except Exception as e:
				core.log_exception()
				break

	def dispose(self) -> None:
		self.process.dispose()


class LLDB(adapter.AdapterConfiguration):

	type = 'lldb'
	docs = 'https://github.com/vadimcn/vscode-lldb/blob/master/MANUAL.md#starting-a-new-debug-session'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		install_path = adapter.vscode.install_path(self.type)

		command = [
			f'{install_path}/extension/adapter/codelldb',
		]

		liblldb = Settings.lldb_library
		if liblldb:
			command.extend(["--liblldb", liblldb])

		process = adapter.Process(command, None)

		try:
			line = await process.readline(process.stdout)
			result = re.match(r'Listening on port (.*)', line.decode('utf-8'))
			port = int(result.group(1))
			return LLDBTransport(process, port, log)
		except:
			process.dispose()
			raise

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		if configuration.request == 'custom':
			configuration.request = 'launch'
			configuration['request'] = 'launch'
			configuration['custom'] = True

		configuration['_adapterSettings'] = self.adapter_settings()

		if 'pid' in configuration and configuration['pid'] == '${command_pick_process}':
			from ..util import select_process
			configuration['pid'] = await select_process()

		return configuration

	async def install(self, log: core.Logger):
		arch = core.platform.architecture

		if core.platform.windows and arch == 'x64':
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-windows.vsix'
		elif core.platform.osx and arch == 'x64':
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-darwin.vsix'
		elif core.platform.osx and arch == 'arm64':
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-aarch64-darwin.vsix'
		elif core.platform.linux and arch == 'x64':
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-linux.vsix'
		elif core.platform.linux and arch == 'arm64':
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-aarch64-linux.vsix'
		else:
			raise core.Error('Your platforms architecture is not supported by vscode lldb. See https://github.com/vadimcn/vscode-lldb/releases/latest')

		await adapter.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await adapter.git.installed_status('vadimcn', 'vscode-lldb', self.installed_version, log)

	@property
	def installed_version(self) -> str|None:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return adapter.vscode.configuration_schema(self.type)

	def adapter_settings(self):
		return {
			'showDisassembly': Settings.lldb_show_disassembly,
			'displayFormat': Settings.lldb_display_format,
			'dereferencePointers': Settings.lldb_dereference_pointers,
		}
		# showDisassembly: 'auto', #'always' | 'auto' | 'never' = 'auto';
		# displayFormat: 'auto', # 'auto' | 'hex' | 'decimal' | 'binary' = 'auto';
		# dereferencePointers: True
		# evaluationTimeout: number;
		# suppressMissingSourceFiles: boolean;
		# consoleMode: 'commands' | 'expressions';
		# sourceLanguages: string[];
		# terminalPromptClear: string[];

	def commands(self):
		from ..debugger import Debugger

		class Command(commands.Command):
			def __init__(self, name: str, command: str, action: Callable):
				self.name = name
				self.command = command
				self.action = action
				self.menus = Command.menu_commands

			def parameters(self, window: sublime.Window):
				return Debugger.get(window),

			def run(self, debugger):
				self.action(debugger)

		return [
			Command(
				'LLDB Toggle Disassembly',
				'lldb_toggle_disassembly',
				lambda debugger: self.toggle_disassembly(debugger.sessions)
			),
			Command(
				'LLDB Display Options',
				'lldb_display',
				lambda debugger: self.display_menu(debugger.sessions).run()
			),
			Command(
				'LLDB Toggle Dereference',
				'lldb_toggle_dereference',
				lambda debugger: self.toggle_deref(debugger.sessions)
			),
		]

	# lldb settings must be resent to the debugger when updated
	# we only resend them when chaging through the ui if not the adapter needs to be restarted
	@core.schedule
	async def updated_settings(self, sessions: dap.Sessions):
		for session in sessions:
			if session.adapter_configuration == self:
				await sessions.active.request('_adapterSettings', self.adapter_settings())

	def toggle_disassembly(self, sessions: dap.Sessions):
		if Settings.lldb_show_disassembly == 'auto':
			Settings.lldb_show_disassembly = 'always'
		else:
			Settings.lldb_show_disassembly = 'auto'

		self.updated_settings(sessions)

	def toggle_deref(self, sessions: dap.Sessions):
		Settings.lldb_dereference_pointers = not Settings.lldb_dereference_pointers
		self.updated_settings(sessions)

	def display_menu(self, sessions: dap.Sessions):
		def set_display(mode: str):
			Settings.lldb_display_format = mode
			self.updated_settings(sessions)

		return ui.InputList([
				ui.InputListItemChecked(lambda: set_display('auto'), 'Auto', 'Auto', Settings.lldb_display_format == 'auto'),
				ui.InputListItemChecked(lambda: set_display('hex'), 'Hex', 'Hex', Settings.lldb_display_format == 'hex'),
				ui.InputListItemChecked(lambda: set_display('decimal'), 'Decimal', 'Decimal', Settings.lldb_display_format == 'decimal'),
				ui.InputListItemChecked(lambda: set_display('binary'), 'Binary', 'Binary', Settings.lldb_display_format == 'binary'),
                ],
			'Display Options'
		)

	def ui(self, sessions: dap.Sessions):
		return InputListView(ui.InputList([
			ui.InputListItemOnOff(lambda: self.toggle_disassembly(sessions), 'Disassembly', 'Disassembly', Settings.lldb_show_disassembly != 'auto'),
		]))
