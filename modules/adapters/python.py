from __future__ import annotations
from ..typecheck import *

from .import util
from .. import dap
from .. import core

import sublime
import shutil

class Python(dap.AdapterConfiguration):

	type = 'python'
	docs = 'https://github.com/microsoft/vscode-docs/blob/main/docs/python/debugging.md#python-debug-configurations-in-visual-studio-code'

	installer = util.OpenVsxInstaller(
		type='python',
		repo='ms-python/python'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		if configuration.request == 'attach':
			connect = configuration.get('connect')
			if connect:
				host = connect.get('host', 'localhost')
				port = connect.get('port')
				return await dap.SocketTransport.connect_with_retry(log, host, port)

			port = configuration.get('port')
			if port:
				host = configuration.get('host', 'localhost')
				return await dap.SocketTransport.connect_with_retry(log, host, port)

			if not configuration.get('listen') and not configuration.get('processId'):
				sublime.error_message('Warning: Check your debugger configuration.\n\n"attach" requires "connect", "listen" or "processId".\n\nIf they contain a $variable that variable may not have existed.')

		install_path = util.vscode.install_path(self.type)

		python = configuration.get('pythonPath') or configuration.get('python')

		if not python:
			if shutil.which('python3'):
				python = shutil.which('python3')
			else:
				python = shutil.which('python')

		if not python:
			raise core.Error('Unable to find `python3` or `python`')

		command = [
			python,
			f'{install_path}/extension/pythonFiles/lib/python/debugpy/adapter',
		]

		return dap.StdioTransport(log, command)

	async def on_custom_event(self, session: dap.Session, event: str, body: Any):
		if event == 'debugpyAttach':
			configuration = dap.Configuration.from_json(body, -1)
			configuration_expanded = dap.ConfigurationExpanded(configuration, session.configuration.variables)
			await session.debugger.launch(session.breakpoints, self, configuration_expanded, parent=session)
		else:
			core.error(f'event ignored not implemented {event}')

	# TODO: patch in env since python seems to not inherit it from the adapter proccess.
	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		if configuration.request == 'launch':
			if not configuration.get('program') and not configuration.get('module'):
				sublime.error_message('Warning: Check your debugger configuration.\n\nBold fields `program` and `module` in configuration are empty. If they contained a $variable that variable may not have existed.')

		return configuration
