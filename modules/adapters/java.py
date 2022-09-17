# Basic idea here is...
# When installing the adapter it would add the com.microsoft.java.debug.plugin-0.30.0.jar as a plugin to lsp-jdts
# When starting the adapter it will ask lsp-jdts to start the adapter by calling the command lsp_jdts_start_debugging exposed by lsp-jdts
# lsp-jdts will then call debugger_lsp_jdts_start_debugging_response after it has started the adapter
# Debugger will then connect to the given port and start debugging

# see https://github.com/Microsoft/java-debug for how the lsp side needs to be setup
# command to start the debug session
#   {
#       'command': 'vscode.java.startDebugSession'
#   }

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

	async def start(self, log, configuration):
		# Make sure LSP and LSP-JDTLS are installed
		pc_settings = sublime.load_settings('Package Control.sublime-settings')
		installed_packages = pc_settings.get('installed_packages', [])
		if 'LSP-jdtls' not in installed_packages or 'LSP' not in installed_packages:
			raise core.Error('LSP and LSP-jdtls required to debug Java!')

		# Get configuration from LSP
		lsp_config = await self.get_configuration_from_lsp()

		# Configure debugger
		if 'cwd' not in configuration:
			configuration['cwd'], _ = os.path.split(sublime.active_window().project_file_name())
		if 'mainClass' not in configuration or not configuration['mainClass']:
			configuration['mainClass'] = lsp_config['mainClass']
		if 'classPaths' not in configuration:
			configuration['classPaths'] = lsp_config['classPaths']
		if 'modulePaths' not in configuration:
			configuration['modulePaths'] = lsp_config['modulePaths']
		if 'console' not in configuration:
			configuration['console'] = 'internalConsole'
		if lsp_config['enablePreview']:
			if 'vmArgs' in configuration:
				configuration['vmArgs'] += ' --enable-preview'
			else:
				configuration['vmArgs'] = '--enable-preview'

		# Start debugging session on the LSP side
		port = await self.lsp_execute_command('vscode.java.startDebugSession')

		return dap.SocketTransport(log, 'localhost', port)

	async def install(self, log):
		url = await util.openvsx.latest_release_vsix('vscjava', 'vscode-java-debug')
		await util.vscode.install(self.type, url, log)

	async def installed_status(self, log):
		return await util.openvsx.installed_status('vscjava', 'vscode-java-debug', self.installed_version)

	@property
	def installed_version(self) -> Optional[str]:
		return util.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> Optional[list]:
		return util.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> Optional[dict]:
		return util.vscode.configuration_schema(self.type)

	async def on_navigate_to_source(self, source: dap.SourceLocation) -> Optional[Tuple[str, str]]:
		if not source.source.path or not source.source.path.startswith('jdt:'):
			return None
		content = await self.get_class_content_for_uri(source.source.path)
		return content, 'text/java'

	async def get_class_content_for_uri(self, uri):
		return await self.lsp_request('java/classFileContents', {'uri': uri})

	async def get_configuration_from_lsp(self) -> dict:
		lsp_config = {}

		mainclass_resp = await self.lsp_execute_command('vscode.java.resolveMainClass')
		if not mainclass_resp or 'mainClass' not in mainclass_resp[0]:
			raise core.Error('Failed to resolve main class')
		else:
			lsp_config['mainClass'] = mainclass_resp[0]['mainClass']
			lsp_config['projectName'] = mainclass_resp[0].get('projectName', '')

		classpath_response = await self.lsp_execute_command(
			'vscode.java.resolveClasspath', [lsp_config['mainClass'], lsp_config['projectName']]
		)
		if not classpath_response[0] and not classpath_response[1]:
			raise core.Error('Failed to resolve classpaths/modulepaths')
		else:
			lsp_config['modulePaths'] = classpath_response[0]
			lsp_config['classPaths'] = classpath_response[1]

		# See https://github.com/microsoft/vscode-java-debug/blob/b2a48319952b1af8a4a328fc95d2891de947df94/src/configurationProvider.ts#L297
		lsp_config['enablePreview'] = await self.lsp_execute_command(
		    'vscode.java.checkProjectSettings',
		    [
                json.dumps(
                    {
                        'className': lsp_config['mainClass'],
                        'projectName': lsp_config['projectName'],
                        'inheritedOptions': True,
                        'expectedOptions': {
                            'org.eclipse.jdt.core.compiler.problem.enablePreviewFeatures': 'enabled'
                        },
                    }
                )
            ]
		)

		return lsp_config

	async def lsp_execute_command(self, command, arguments=None):
		request_params = { 'command': command }
		if arguments:
			request_params['arguments'] = arguments
		return await self.lsp_request('workspace/executeCommand', request_params)

	async def lsp_request(self, method, params) -> Any:
		'''
		Returns the response or raises an exception.
		'''

		# probably need to add some sort of timeout
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

		command_response = await future

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
