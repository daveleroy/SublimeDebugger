from __future__ import annotations
import os
from typing import Any

from .. import core
from .. import dap
from . import util


class JavaScriptAdapter(dap.Adapter):
	type = []

	docs = 'https://github.com/microsoft/vscode-js-debug/blob/main/OPTIONS.md'

	installer = util.GitInstaller(type='js', repo='daveleroy/vscode-js-debug')

	pending_target_parents: dict[str, dap.Session] = {}
	sessions: dict[dap.Session, Any] = {}

	@property
	def configuration_snippets(self):
		return self.installer.configuration_snippets(self.types[0])

	@property
	def configuration_schema(self):
		return self.installer.configuration_schema(self.types[0])

	async def start(self, console: dap.Console, configuration: dap.ConfigurationExpanded):
		__jsDebugChildServer = configuration.get('__jsDebugChildServer')

		if __jsDebugChildServer is not None:
			server = int(__jsDebugChildServer)
			return dap.SocketTransport('localhost', server)

		node = await util.get_and_warn_require_node(self.type, console)
		install_path = self.installer.install_path()

		port = util.get_open_port()

		# version >= 1.77.2
		if os.path.exists(f'{install_path}/src/vsDebugServer.js'):
			command = [
				node,
				f'{install_path}/src/vsDebugServer.js',
				f'{port}',
			]

		# version < 1.77.2
		else:
			command = [
				node,
				f'{install_path}/src/vsDebugServer.bundle.js',
				f'{port}',
			]

		return dap.SocketTransport(command=command, port=port)

	async def on_custom_request(self, session: dap.Session, command: str, arguments: Any) -> Any:
		if command == 'attachedChildSession':
			debugger = session.debugger
			config = dap.Configuration.from_json(arguments['config'], 0)
			await debugger.launch(self, await config.Expanded([], session.configuration.variables), parent=session)
			return {}

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		# not sure if this is still required?
		configuration['type'] = f'pwa-{self.types[0]}'

		configuration['__workspaceFolder'] = await configuration.variables['folder']
		return configuration


class Node(JavaScriptAdapter):
	type = 'node'
class Chrome(JavaScriptAdapter):
	type = 'chrome'
	docs = 'https://github.com/Microsoft/vscode-chrome-debug#using-the-debugger'


class Edge(JavaScriptAdapter):
	type = 'msedge'
