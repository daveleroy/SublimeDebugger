from __future__ import annotations
from typing import Any

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

	docs = 'https://github.com/microsoft/vscode-js-debug/blob/main/OPTIONS.md'

	installer = util.GitInstaller (
		type='js',  
		repo='daveleroy/vscode-js-debug'
	)
	
	pending_target_parents: dict[str, dap.Session] = {}
	sessions: dict[dap.Session, Any] = {}

	@property
	def configuration_snippets(self):
		return util.vscode.configuration_snippets('js', self.type_internal)

	@property
	def configuration_schema(self):
		return util.vscode.configuration_schema('js', self.type_internal)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		__jsDebugChildServer = configuration.get('__jsDebugChildServer')

		if __jsDebugChildServer is not None:
			server = int(__jsDebugChildServer)
			transport = dap.SocketTransport(log, 'localhost', server)
			return transport

		node = await util.get_and_warn_require_node(self.type, log)
		install_path = util.vscode.install_path('js')

		port = util.get_open_port()

		command = [
			node,
			f'{install_path}/extension/src/vsDebugServer.bundle.js',
			f'{port}',
		]

		return await dap.SocketTransport.connect_with_process(log, command, port)

	async def on_custom_request(self, session: dap.Session, command: str, arguments: Any) -> Any:
		if command == 'attachedChildSession':
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
