from __future__ import annotations
from ..typecheck import *

from ..import core
from ..import dap

from .import util

import re


class Transport(dap.SocketTransport):
	def __init__(self, log: core.Logger, process: Any, port: int):
		super().__init__(log, 'localhost', port)
		self.process = process

	def dispose(self) -> None:
		self.process.dispose()


class JSAdapterConfiguration(dap.AdapterConfiguration):
	type = 'js'
	type_internal = 'js'

	development = True
	docs = 'https://github.com/microsoft/vscode-js-debug/blob/main/OPTIONS.md'

	
	pending_target_parents: dict[str, dap.Session] = {}

	sessions: dict[dap.Session, Any] = {}

	@property
	def info(self): return util.vscode.info('js')

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets('js', self.type_internal)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema('js', self.type_internal)

	async def install(self, log: core.Logger):
		url = await util.git.latest_release_vsix('daveleroy', 'vscode-js-debug')
		await util.vscode.install('js', url, log)

	async def installed_status(self, log: core.Logger):
		return await util.git.installed_status('daveleroy', 'vscode-js-debug', self.installed_version, log)

	@property
	def installed_version(self) -> str|None:
		return util.vscode.installed_version('js')

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		__jsDebugChildServer = configuration.get('__jsDebugChildServer')

		if __jsDebugChildServer is not None:
			server = int(__jsDebugChildServer)
			transport = dap.SocketTransport(log, 'localhost', server)
			return transport

		node = await util.get_and_warn_require_node(self.type, log)
		install_path = util.vscode.install_path('js')
		command = [
			node,
			# '/Users/david/Desktop/vscode-js-debug-master 3/dist/src/vsDebugServer.js'
			f'{install_path}/extension/src/vsDebugServer.bundle.js'
		]

		process = dap.Process(command, None)

		try:
			try:
				line = (await process.readline(process.stdout)).decode('utf-8')
				# result = re.match(r'Debug server listening at (.*)', line)
				result = re.match(r'(.*)', line)
				if not result:
					raise core.Error(f'Unable to parse debug server port from line: {line}')

				port = int(result.group(1))
				return Transport(log, process, port)

			except EOFError:
				...

			# read out stderr there might be something interesting here
			try:
				while True:
					line = await process.readline(process.stderr)
					log.error(line.decode('utf-8'))

			except EOFError:
				...

			raise core.Error("Unable to find debug server port")

		except:
			process.dispose()
			raise

	async def on_custom_request(self, session: dap.Session, request: str, arguments: Any) -> Any:
		if request == 'attachedChildSession':
			debugger = session.debugger
			config = dap.Configuration.from_json(arguments['config'], 0)
			await debugger.launch(session.breakpoints, self, dap.ConfigurationExpanded(config, session.configuration.variables), parent=session)
			return {}

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		configuration['type'] = self.type_internal
		configuration['__workspaceFolder'] = configuration.variables['folder']
		return configuration


class Chrome (JSAdapterConfiguration):
	type = 'chrome'
	type_internal = 'pwa-chrome'
	docs = 'https://github.com/Microsoft/vscode-chrome-debug#using-the-debugger'
	development = False


class Node (JSAdapterConfiguration):
	type = 'node'
	type_internal = 'pwa-node'
	development = False


class Edge (JSAdapterConfiguration):
	type = 'msedge'
	type_internal = 'pwa-msedge'
	development = False
