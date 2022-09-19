from ..typecheck import Optional, Dict, Any, Tuple
from ..import core
from ..import dap
from .import util

import sublime
import sublime_plugin
import os
import json


class Java(dap.AdapterConfiguration):
	jdtls_bridge: Dict[int, core.Future] = {}
	jdtls_bridge_current_id = 0

	type = 'java'
	docs = 'https://github.com/redhat-developer/vscode-java/blob/master/README.md'

	installer = util.OpenVsxInstaller(
		type='java',
		repo='vscjava/vscode-java-debug'
	)

	async def start(self, log, configuration):
		# Make sure LSP and LSP-JDTLS are installed
		pc_settings = sublime.load_settings('Package Control.sublime-settings')
		installed_packages = pc_settings.get('installed_packages', [])
		if 'LSP-jdtls' not in installed_packages or 'LSP' not in installed_packages:
			raise core.Error('LSP and LSP-jdtls required to debug Java!')

		# Configure debugger
		def _is_undefined(key):
			return key not in configuration or isinstance(configuration[key], str) and not configuration[key]

		if _is_undefined('cwd'):
			configuration['cwd'], _ = os.path.split(sublime.active_window().project_file_name())
		if _is_undefined('console'):
			configuration['console'] = 'internalConsole'

		configuration['mainClass'], configuration['projectName'] = await self._get_mainclass_project_name(None if _is_undefined('mainClass') else configuration['mainClass'])
		if _is_undefined('classPaths') and _is_undefined('modulePaths'):
			configuration['modulePaths'], configuration['classPaths'] = await self._resolve_modulepath_classpath(configuration['mainClass'], configuration['projectName'])
		if await self._is_preview_enabled(configuration['mainClass'], configuration['projectName']):
			if 'vmArgs' in configuration:
				configuration['vmArgs'] += ' --enable-preview'
			else:
				configuration['vmArgs'] = '--enable-preview'

		# Start debugging session on the LSP side
		port = await self.lsp_execute_command('vscode.java.startDebugSession')

		return dap.SocketTransport(log, 'localhost', port)

	async def on_navigate_to_source(self, source: dap.SourceLocation) -> Optional[Tuple[str, str]]:
		if not source.source.path or not source.source.path.startswith('jdt:'):
			return None
		content = await self.get_class_content_for_uri(source.source.path)
		return content, 'text/java'

	async def get_class_content_for_uri(self, uri):
		return await self.lsp_request('java/classFileContents', {'uri': uri})

	async def _get_mainclass_project_name(self, preferred_mainclass=None):
		mainclasses = await self.lsp_execute_command('vscode.java.resolveMainClass')
		if not mainclasses:
			raise core.Error('Failed to resolve main class')

		if preferred_mainclass:
			matches = [x for x in mainclasses if x['mainClass'] == preferred_mainclass]
			if matches:
				return matches[0]['mainClass'], matches[0]['projectName']
			else:
				raise core.Error('Mainclass {} not found. Check your debugger configuration or leave "mainClass" empty to detect the mainclass automatically'.format(preferred_mainclass))

		if len(mainclasses) == 1:
			return mainclasses[0]['mainClass'], mainclasses[0]['projectName']

		# Show panel
		future_index = core.Future()
		items = [sublime.QuickPanelItem(x['mainClass'], x['filePath'], "", (3, "", "")) for x in mainclasses]
		if sublime.version() < '4081':
			sublime.active_window().show_quick_panel(items, lambda idx: future_index.set_result(idx), sublime.MONOSPACE_FONT | sublime.KEEP_OPEN_ON_FOCUS_LOST)
		else:
			sublime.active_window().show_quick_panel(items, lambda idx: future_index.set_result(idx), sublime.MONOSPACE_FONT | sublime.KEEP_OPEN_ON_FOCUS_LOST, placeholder="Select Mainclass")
		index = await future_index

		if index == -1:
			raise core.Error("Please specify a main class")

		return mainclasses[index]['mainClass'], mainclasses[index]['projectName']

	async def _resolve_modulepath_classpath(self, main_class, project_name):
		classpath_response = await self.lsp_execute_command(
			'vscode.java.resolveClasspath', [main_class, project_name]
		)
		if not classpath_response[0] and not classpath_response[1]:
			raise core.Error('Failed to resolve classpaths/modulepaths automatically, please specify the value in the debugger configuration')

		module_paths = classpath_response[0]
		class_paths = classpath_response[1]
		return module_paths, class_paths


	async def _is_preview_enabled(self, main_class, project_name) -> dict:
		# See https://github.com/microsoft/vscode-java-debug/blob/b2a48319952b1af8a4a328fc95d2891de947df94/src/configurationProvider.ts#L297
		return await self.lsp_execute_command(
		    'vscode.java.checkProjectSettings',
		    [
                json.dumps(
                    {
                        'className': main_class,
                        'projectName': project_name,
                        'inheritedOptions': True,
                        'expectedOptions': {
                            'org.eclipse.jdt.core.compiler.problem.enablePreviewFeatures': 'enabled'
                        },
                    }
                )
            ]
		)

	async def lsp_execute_command(self, command, arguments=None):
		request_params = { 'command': command }
		if arguments:
			request_params['arguments'] = arguments
		return await self.lsp_request('workspace/executeCommand', request_params)

	async def lsp_request(self, method, params) -> Any:
		'''
		Returns the response or raises an exception.
		'''
		future = core.Future()

		id = Java.jdtls_bridge_current_id
		Java.jdtls_bridge_current_id += 1
		Java.jdtls_bridge[id] = future

		# Send a request to JDTLS.
		# NOTE: the active window might not match the debugger window but generally will
		# TODO: a way to get the actual window.
		sublime.active_window().run_command(
			'debugger_jdtls_bridge_request',
			{'id': id, 'callback_command': 'debugger_jdtls_bridge_response', 'method': method, 'params': params}
		)
		sublime.set_timeout(lambda: future.cancel(), 2500)
		try:
			command_response = await future
		except core.CancelledError:
			raise core.Error('Unable to connect to LSP-jdtls (timed out)')

		del Java.jdtls_bridge[id]

		if command_response['error']:
			raise core.Error(command_response['error'])
		return command_response['resp']


class DebuggerJdtlsBridgeResponseCommand(sublime_plugin.WindowCommand):
	def run(self, **args):
		future = Java.jdtls_bridge.get(args['id'])
		if not future:
			print('Unable to find a future for this id')
			return
		future.set_result(args)
