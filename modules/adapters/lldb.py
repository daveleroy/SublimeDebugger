from __future__ import annotations

from ..typecheck import *

from ..import core
from ..import ui

from ..debugger import dap
from ..views.input_list_view import InputListView

from ..import commands
from ..import settings

from .import util


class LLDBCommands(commands.Commands):
	lldb_toggle_disassembly = commands.CommandDebugger(
		'LLDB Toggle Disassembly',
		lambda debugger: LLDB.toggle_disassembly(debugger)
	)
	lldb_display = commands.CommandDebugger(
		'LLDB Display Options',
		lambda debugger: LLDB.display_menu(debugger).run()
	)
	lldb_toggle_dereference = commands.CommandDebugger(
		'LLDB Toggle Dereference',
		lambda debugger: LLDB.toggle_deref(debugger)
	)


class LLDBSettings(settings.Settings):
	lldb_show_disassembly: str = 'auto'
	lldb_display_format: str = 'auto'
	lldb_dereference_pointers: bool = True
	lldb_library: str|None = None
	lldb_python: str|None = None

class LLDB(dap.AdapterConfiguration):

	type = 'lldb'
	docs = 'https://github.com/vadimcn/vscode-lldb/blob/master/MANUAL.md#starting-a-new-debug-session'


	# toggle_disassembly = commands.CommandDebugger(
	# 	'LLDB Toggle Disassembly',
	# 	lambda debugger: LLDB.toggle_disassembly(debugger)
	# )

	# display = commands.CommandDebugger(
	# 	'LLDB Display Options',
	# 	lambda debugger: LLDB.display_menu(debugger).run()
	# )
	# toggle_dereference = commands.CommandDebugger(
	# 	'LLDB Toggle Dereference',
	# 	lambda debugger: LLDB.toggle_deref(debugger)
	# )

	# show_disassembly: str = settings.Setting(
	# 	'auto',
	# 	description
	# )

	# display_format: str = settings.Setting('auto')

	dereference_pointers: bool = True
	library: str|None = None
	python: str|None = None

	

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		install_path = util.vscode.install_path(self.type)
		port = util.get_open_port()
		command = [
			f'{install_path}/extension/adapter/codelldb',
			f'--port',
			f'{port}',
		]

		liblldb = LLDBSettings.lldb_library
		if liblldb:
			command.extend(['--liblldb', liblldb])

		return await dap.SocketTransport.connect_with_process(log, command, port)

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

		await util.vscode.install(self.type, url, log)

	async def installed_status(self, log: core.Logger):
		return await util.git.installed_status('vadimcn', 'vscode-lldb', self.installed_version, log)

	@property
	def installed_version(self) -> str|None:
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema(self.type)

	@staticmethod
	def adapter_settings():
		return {
			'showDisassembly': LLDBSettings.lldb_show_disassembly,
			'displayFormat': LLDBSettings.lldb_display_format,
			'dereferencePointers': LLDBSettings.lldb_dereference_pointers,
		}
		# showDisassembly: 'auto', #'always' | 'auto' | 'never' = 'auto';
		# displayFormat: 'auto', # 'auto' | 'hex' | 'decimal' | 'binary' = 'auto';
		# dereferencePointers: True
		# evaluationTimeout: number;
		# suppressMissingSourceFiles: boolean;
		# consoleMode: 'commands' | 'expressions';
		# sourceLanguages: string[];
		# terminalPromptClear: string[];

	# lldb settings must be resent to the debugger when updated
	# we only resend them when chaging through the ui if not the adapter needs to be restarted
	@staticmethod
	@core.schedule
	async def updated_settings(debugger: dap.Debugger):
		for session in debugger.sessions:
			if session.adapter_configuration.type == LLDB.type:
				await session.request('_adapterSettings', LLDB.adapter_settings())

	@staticmethod
	def toggle_disassembly(debugger: dap.Debugger):
		print('toggle_disassembly')
		if LLDBSettings.lldb_show_disassembly == 'auto':
			LLDBSettings.lldb_show_disassembly = 'always'
		else:
			LLDBSettings.lldb_show_disassembly = 'auto'

		LLDB.updated_settings(debugger)

	@staticmethod
	def toggle_deref(debugger: dap.Debugger):
		LLDBSettings.lldb_dereference_pointers = not LLDBSettings.lldb_dereference_pointers
		LLDB.updated_settings(debugger)

	@staticmethod
	def display_menu(debugger: dap.Debugger):
		def set_display(mode: str):
			LLDBSettings.lldb_display_format = mode
			LLDB.updated_settings(debugger)

		return ui.InputList([
				ui.InputListItemChecked(lambda: set_display('auto'), LLDBSettings.lldb_display_format == 'auto', 'Auto', 'Auto'),
				ui.InputListItemChecked(lambda: set_display('hex'), LLDBSettings.lldb_display_format == 'hex', 'Hex', 'Hex'),
				ui.InputListItemChecked(lambda: set_display('decimal'), LLDBSettings.lldb_display_format == 'decimal', 'Decimal', 'Decimal'),
				ui.InputListItemChecked(lambda: set_display('binary'), LLDBSettings.lldb_display_format == 'binary', 'Binary', 'Binary'),
			],
			'Display Options'
		)

	def ui(self, debugger: dap.Debugger):
		return InputListView(ui.InputList([
			ui.InputListItemOnOff(lambda: self.toggle_disassembly(debugger), 'Disassembly', 'Disassembly', LLDBSettings.lldb_show_disassembly != 'auto'),
		]))
