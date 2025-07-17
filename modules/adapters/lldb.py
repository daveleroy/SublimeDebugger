from __future__ import annotations

from .. import core
from .. import ui
from .. import dap

from .. import settings
from .. import command
from . import util


def is_valid_asset(asset: str):
	arch = core.platform.architecture
	if core.platform.windows and arch == 'x64':
		return asset.endswith('-x86_64-windows.vsix')
	elif core.platform.osx and arch == 'x64':
		return asset.endswith('-x86_64-darwin.vsix')
	elif core.platform.osx and arch == 'arm64':
		return asset.endswith('-aarch64-darwin.vsix')
	elif core.platform.linux and arch == 'x64':
		return asset.endswith('-x86_64-linux.vsix')
	elif core.platform.linux and arch == 'arm64':
		return asset.endswith('-aarch64-linux.vsix')
	else:
		raise dap.Error('Your platforms architecture is not supported by vscode lldb. See https://github.com/vadimcn/vscode-lldb/releases/latest')


class LLDB(dap.Adapter):
	type = 'lldb'
	docs = 'https://github.com/vadimcn/vscode-lldb/blob/master/MANUAL.md#starting-a-new-debug-session'

	installer = util.GitInstaller(
		type='lldb',
		repo='vadimcn/vscode-lldb',
		is_valid_asset=is_valid_asset,
	)

	lldb_display_format = settings.Setting[str](
		key='lldb_display_format',
		default='auto',
		visible=False,
	)
	lldb_dereference_pointers = settings.Setting[bool](
		key='lldb_dereference_pointers',
		default=True,
		visible=False,
	)
	lldb_library = settings.Setting['str|None'](
		key='lldb_library',
		default=None,
		description='Which lldb library to use',
	)

	async def start(self, console: dap.Console, configuration: dap.ConfigurationExpanded):
		install_path = self.installer.install_path()
		port = util.get_open_port()
		command = [f'{install_path}/adapter/codelldb', f'--port', f'{port}']

		liblldb = LLDB.lldb_library
		if liblldb:
			command.extend(['--liblldb', liblldb])

		if 'sourceLanguages' in configuration:
			import json

			command.extend(
				[
					'--settings',
					json.dumps({'sourceLanguages': configuration['sourceLanguages']}),
				]
			)

			del configuration['sourceLanguages']

		return dap.SocketTransport(command=command, port=port)

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		if configuration.request == 'custom':
			configuration.request = 'launch'
			configuration['request'] = 'launch'
			configuration['custom'] = True

		configuration['_adapterSettings'] = self.adapter_settings()
		return configuration

	@staticmethod
	def adapter_settings():
		return {
			'displayFormat': LLDB.lldb_display_format,
			'dereferencePointers': LLDB.lldb_dereference_pointers,
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
	@core.run
	async def updated_settings(debugger: dap.Debugger) -> None:
		for session in debugger.sessions:
			if session.adapter.type == LLDB.type:
				await session.request('_adapterSettings', LLDB.adapter_settings())

	@staticmethod
	def toggle_deref(debugger: dap.Debugger):
		LLDB.lldb_dereference_pointers = not LLDB.lldb_dereference_pointers
		LLDB.updated_settings(debugger)

	@staticmethod
	def display_menu(debugger: dap.Debugger):
		def set_display(mode: str):
			LLDB.lldb_display_format = mode
			LLDB.updated_settings(debugger)

		return ui.InputList('Display Options')[
			ui.InputListItemChecked(lambda: set_display('auto'), LLDB.lldb_display_format == 'auto', 'Auto', 'Auto'),
			ui.InputListItemChecked(lambda: set_display('hex'), LLDB.lldb_display_format == 'hex', 'Hex', 'Hex'),
			ui.InputListItemChecked(lambda: set_display('decimal'), LLDB.lldb_display_format == 'decimal', 'Decimal', 'Decimal'),
			ui.InputListItemChecked(lambda: set_display('binary'), LLDB.lldb_display_format == 'binary', 'Binary', 'Binary'),
		]


class LLDBDisplayOptions(command.Action):
	name = 'LLDB: Display Options'
	key = 'lldb_display'

	@core.run
	async def action(self, debugger: dap.Debugger):
		await LLDB.display_menu(debugger)


class LLDBToggleDereference(command.Action):
	name = 'LLDB: Toggle Dereference'
	key = 'lldb_toggle_dereference'

	def action(self, debugger: dap.Debugger):
		LLDB.lldb_dereference_pointers = not LLDB.lldb_dereference_pointers
		LLDB.updated_settings(debugger)
