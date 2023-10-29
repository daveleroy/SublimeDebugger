from __future__ import annotations
from typing import Any

from ..import core
from ..import dap
from .import util

import sublime
import json


class Java(dap.AdapterConfiguration):
	type = 'java'
	docs = 'https://github.com/redhat-developer/vscode-java/blob/master/README.md'

	installer = util.GitInstaller(
		type='java',
		repo='microsoft/vscode-java-debug'
	)

	async def start(self, log, configuration):
		# Make sure LSP and LSP-JDTLS are installed
		util.require_package('LSP-jdtls')
		util.require_package('LSP')

		# Configure debugger
		def _is_undefined(key):
			return key not in configuration or isinstance(configuration[key], str) and not configuration[key]

		if _is_undefined('cwd'):
			configuration['cwd'] = configuration.variables.get('folder')
		if _is_undefined('console'):
			configuration['console'] = 'internalConsole'

		if _is_undefined('mainClass') or _is_undefined("projectName"):
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

		return dap.SocketTransport('localhost', port)

	async def on_navigate_to_source(self, source: dap.SourceLocation) -> tuple[str, str, list[tuple[str, Any]]]|None:
		if not source.source.path or not source.source.path.startswith('jdt:'):
			return None
		content = await self.get_class_content_for_uri(source.source.path)
		return content, 'text/java', [("lsp_uri", source.source.path)]

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
		# Preselect mainclass associated with active view
		selected_index = -1
		view = sublime.active_window().active_view()
		if view:
			for i, mainclass in enumerate(mainclasses):
				if mainclass['filePath'] == view.file_name():
					selected_index = i
					break
		if sublime.version() < '4081':
			sublime.active_window().show_quick_panel(items,
			                                         lambda idx: future_index.set_result(idx),
			                                         sublime.MONOSPACE_FONT | sublime.KEEP_OPEN_ON_FOCUS_LOST,
			                                         selected_index)
		else:
			sublime.active_window().show_quick_panel(items,
			                                         lambda idx: future_index.set_result(idx),
			                                         sublime.MONOSPACE_FONT | sublime.KEEP_OPEN_ON_FOCUS_LOST,
			                                         selected_index,
			                                         placeholder="Select Mainclass")
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
		return await self.lsp_request('workspace/executeCommand', {
			'command': command,
			'arguments': arguments
		})

	async def lsp_request(self, method, params) -> Any:
		return await util.lsp.request('jdtls', method, params)
