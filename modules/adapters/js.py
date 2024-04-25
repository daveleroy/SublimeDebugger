from __future__ import annotations
import os
from typing import Any

from ..import core
from ..import dap

from .import util

class JSAdapterConfiguration(dap.AdapterConfiguration):
	type = []

	# This type is the one sent to the debug adapter
	# It should be overriden in each subclass (see below)
	configuration_type = 'js'

	docs = 'https://github.com/microsoft/vscode-js-debug/blob/main/OPTIONS.md'

	installer = util.GitInstaller (
		type='js',
		repo='daveleroy/vscode-js-debug'
	)

	pending_target_parents: dict[str, dap.Session] = {}
	sessions: dict[dap.Session, Any] = {}

	@property
	def configuration_snippets(self):
		return self.installer.configuration_snippets(self.configuration_type)

	@property
	def configuration_schema(self):
		return self.installer.configuration_schema(self.configuration_type)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		__jsDebugChildServer = configuration.get('__jsDebugChildServer')

		if __jsDebugChildServer is not None:
			server = int(__jsDebugChildServer)
			return dap.SocketTransport('localhost', server)

		node = await util.get_and_warn_require_node(self.type, log)
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
			await debugger.launch(session.breakpoints, self, dap.ConfigurationExpanded(config, session.configuration.variables), parent=session)
			return {}

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		configuration['type'] = self.configuration_type
		configuration['__workspaceFolder'] = configuration.variables['folder']
		return configuration


class Chrome (JSAdapterConfiguration):
	type = 'chrome'
	configuration_type = 'pwa-chrome'
	docs = 'https://github.com/Microsoft/vscode-chrome-debug#using-the-debugger'


class Node (JSAdapterConfiguration):
	type = 'node'
	configuration_type = 'pwa-node'


class Edge (JSAdapterConfiguration):
	type = 'msedge'
	configuration_type = 'pwa-msedge'
