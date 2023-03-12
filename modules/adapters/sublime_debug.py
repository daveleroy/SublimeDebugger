from __future__ import annotations
from dataclasses import dataclass
import socket
from typing import Any, TextIO
import threading

from .util import request

from .import util
from .. import dap
from .. import core

import sublime
import os


initial_preferences = '''{
	"theme": "Debugger.sublime-theme",
}
'''

theme = '''{{
	"extends": "{}",
	"rules": [
		{{
			"class": "status_bar",
			"layer0.tint": "#066592",
		}}
	]
}}
'''


class SublimeInstaller(dap.AdapterInstaller):
	type = 'sublime'

	@property
	def debug_app_name(self):
		platform = sublime.platform()
		if platform == 'osx':
			return 'Sublime Text (Debug).app'
		else:
			return 'Sublime Text (Debug)' # no idea what this is supposed to be on Windows/Linux

	def installed_version(self):
		if os.path.exists(self.install_path()):
			return sublime.version() # might be wrong version
		return None

	async def install(self, version: str | None, log: core.Logger) -> None:
		platform = sublime.platform()
		arch = sublime.arch()

		path = self.temporary_install_path()

		if platform == 'osx':
			await request.download_and_extract_zip(f'https://download.sublimetext.com/sublime_text_build_{sublime.version()}_mac.zip', f'{path}/{self.debug_app_name}', log)
		elif platform == 'windows' and arch =='x64':
			await request.download_and_extract_zip(f'https://download.sublimetext.com/sublime_text_build_{sublime.version()}_x64.zip', f'{path}/{self.debug_app_name}', log)
		else:
			raise core.Error('Install for this platform/arch is not currently supported')

		await request.download_and_extract_zip('https://github.com/microsoft/debugpy/archive/refs/tags/v1.6.6.zip', f'{path}/debugpy', log)
		await request.download_and_extract_zip('https://github.com/daveleroy/debugpy/archive/refs/tags/v1.5.1.zip', f'{path}/debugpy_for_3.3', log)

	async def installable_versions(self, log: core.Logger) -> list[str]:
		return [sublime.version()]


class Sublime(dap.AdapterConfiguration):

	type = 'sublime'
	docs = 'https://github.com/microsoft/vscode-docs/blob/main/docs/python/debugging.md#python-debug-configurations-in-visual-studio-code'
	installer = SublimeInstaller()

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		if configuration.request == 'attach':
			return await dap.SocketTransport.connect_with_retry(log, 'localhost', configuration['port'])

		return SublimeDebugTransport(configuration, log)
	async def on_custom_event(self, session: dap.Session, event: str, body: Any):
		if event == 'attach':
			configuration = dap.Configuration.from_json(body, -1)
			configuration_expanded = dap.ConfigurationExpanded(configuration, session.configuration.variables)
			await session.debugger.launch(session.breakpoints, self, configuration_expanded, parent=session)
	@property
	def configuration_snippets(self):
		keys = {
			'osx': 'OSX',
			'windows': 'Windows',
			'linux': 'Linux',
		}
		platform_key = keys[sublime.platform()]

		return [{
			'name': 'Sublime Plugin Debug',
			'type': 'sublime',
			'request': 'launch',
			'args': [
				'${project_path}'
			],
			'linked_packages': [
				'Debugger',
				f'User/Default ({platform_key}).sublime-keymap',
			]
		}]

	@property
	def configuration_schema(self):
		return {
			'launch': {
				'required': [
					'linked_packages'
				],
				'properties': {
					'args': {
						'type': 'array',
						'description': 'Command line arguments passed to the sublime_text executable',
						'items': {
							'type': 'string'
						},
						'default': []
					},

					'linked_packages': {
						'type': 'array',
						'description': 'Folders/files that will be symlinked into /Packages directory during debugging',
						'items': {
							'type': 'string'
						},
						'default': []
					},
				}
			}
		}


@dataclass
class Client:
	file: TextIO
	socket: socket.socket

	def close(self):
		self.socket.close()


class SublimeDebugTransport(dap.TransportProtocol, dap.Transport):
	def __init__(self, configuration: dap.ConfigurationExpanded, log: core.Logger) -> None:
		super().__init__(self)

		install_path = Sublime.installer.install_path()
		data_directory = f'{install_path}/Data'
		packages_directory = f'{install_path}/Data/Packages'
		origin_packages_directory = sublime.packages_path()

		if sublime.platform() == 'osx':
			sublime_text_directory = f'{install_path}/{Sublime.installer.debug_app_name}/Contents/MacOS'
		elif sublime.platform() == 'windows':
			sublime_text_directory = f'{install_path}/{Sublime.installer.debug_app_name}'
		else:
			raise core.Error('Install for this platform/arch is not currently supported')

		sublime_text_data_directory = f'{sublime_text_directory}/Data'

		core.make_directory(data_directory)
		core.make_directory(f'{data_directory}/Packages')
		core.make_directory(f'{data_directory}/Packages/User')
		core.make_directory(f'{data_directory}/Lib')
		core.make_directory(f'{data_directory}/Lib/Python33')
		core.make_directory(f'{data_directory}/Lib/Python38')

		# we put the data folder outside of the app so its easier to find and at the top level of the adapter install location
		core.symlink(data_directory, sublime_text_data_directory)

		# Add debugpy library for both runtimes
		core.symlink(f'{install_path}/debugpy_for_3.3/src/debugpy', f'{data_directory}/Lib/Python33/debugpy')
		core.symlink(f'{install_path}/debugpy/src/debugpy', f'{data_directory}/Lib/Python38/debugpy')

		# Add sublime_debug_runtime library for both runtimes
		adapters_path =  os.path.dirname(os.path.realpath(__file__))
		core.symlink(f'{adapters_path}/sublime_debug_runtime.py', f'{data_directory}/Lib/Python33/sublime_debug_runtime.py')
		core.symlink(f'{adapters_path}/sublime_debug_runtime.py', f'{data_directory}/Lib/Python38/sublime_debug_runtime.py')


		# Add plugin that initializes the sublime_debug_runtime module before any other packages so it can attach debugpy before any other user packages get loaded
		core.make_directory(f'{data_directory}/Packages/0_sublime_debug_runtime')
		core.write(f'{packages_directory}/0_sublime_debug_runtime/__init__.py', 'import sublime_debug_runtime', overwrite_existing=True)
		core.write(f'{packages_directory}/0_sublime_debug_runtime/.python-version', '3.8', overwrite_existing=True)

		core.make_directory(f'{data_directory}/Packages/0_sublime_debug_runtime_33')
		core.write(f'{packages_directory}/0_sublime_debug_runtime_33/__init__.py', 'import sublime_debug_runtime', overwrite_existing=True)
		core.write(f'{packages_directory}/0_sublime_debug_runtime_33/.python-version', '3.3', overwrite_existing=True)


		linked_packages = configuration.get('linked_packages', [])
		if not linked_packages:
			log.warn('`linked_packages` is empty no packages will be symlinked for debugging purposes.')

		for filename in os.listdir(packages_directory):
			full = os.path.join(packages_directory, filename)
			if os.path.islink(full):
				log.info(f'Removing symlink: {filename}')
				os.remove(full)

		path_mappings = []

		# add symbolic links to the packages you want
		for package in linked_packages:
			if not os.path.isabs(package):
				package = f'{origin_packages_directory}/{package}'

			name = os.path.basename(package)

			log.info(f'Adding symlink: {name} from {package}')
			core.symlink(package, f'{packages_directory}/{name}')

			path_mappings.append({
				'localRoot': package,
				'remoteRoot': f'{packages_directory}/{name}',
			})


		core.write(f'{packages_directory}/User/Preferences.sublime-settings', initial_preferences)

		settings = sublime.load_settings('Preferences.sublime-settings')
		core.write(f'{packages_directory}/User/Debugger.sublime-theme', theme.format(settings.get("theme")), overwrite_existing=True)

		# grab open ports for debugpy
		port = util.get_open_port()

		commands = [f'{sublime_text_directory}/sublime_text', '--multiinstance']
		commands.extend(configuration.get('args', []))

		self.log = log
		self.port = port
		self.path_mappings = path_mappings

		self.clients: list[Client] = []

		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.bind(('localhost', self.port))
		self.socket.listen()

		self.connections = [
			self.accept_connections()
		]

		log.info('Starting `Sublime Text (Debug)`')
		self.process = dap.Process(commands,
		env={
			'sublime_debug_runtime_port': f'{port}',
		})


	def start(self, listener: dap.TransportProtocolListener, log: core.Logger):
		self.events = listener
		self.log = log

	def attach(self, name: str, host: str, port: int):
		self.events.on_event('attach', {
			'type': 'sublime',
			'request': 'attach',
			'name': name,
			'host': host,
			'port': port,
			'justMyCode': False,
			'redirectOutput': True,
			'pathMappings': self.path_mappings,
		})

	@core.run
	async def accept_connections(self):
		async def read(connection: socket.socket, port: int):
			future = core.Future()
			self.connections.append(future)

			self.log.warn(f'sublime_debug_runtime: {port} connected ')

			file = connection.makefile('wr')
			client = Client(file, connection)
			self.clients.append(client)

			while line := await core.run_in_executor(lambda: file.readline())():

				data = core.json_decode(line)

				event = data.get('event')
				body = data.get('body', {})

				if event == 'attach':
					self.log.info(str(data))
					self.attach(body['name'], body['host'], body['port'])
				else:
					self.log.info(str(data))

			self.log.warn(f'sublime_debug_runtime: {port} disconnected')
			future.set_result(None)

		self.log.warn('Waiting on sublime_debug_runtime clients...')
		while True:
			try:
				connection, addr = await core.run_in_executor(lambda: self.socket.accept())()
				core.run(read(connection, addr[1]))
			except:
				break

	async def initialized(self):
		self.events.on_event('initialized', core.JSON({}))

	# TODO: Respond to more requests so this actually implements the protocol correctly
	async def send_request(self, command: str, args: dict[str, Any]|None) -> dict[str, Any]:
		if command == 'initialize':
			# send the initialized event
			core.run(self.initialized())

			return core.JSON({
				# respond with the same filters that our debugpy sessions will have but default userUnhandled to True since I think that should be on by default
				"exceptionBreakpointFilters": [
					core.JSON({"filter": "raised", "label": "Raised Exceptions", "default": False, "description": "Break whenever any exception is raised."}),
					core.JSON({"filter": "uncaught", "label": "Uncaught Exceptions", "default": True, "description": "Break when the process is exiting due to unhandled exception."}),
					core.JSON({"filter": "userUnhandled", "label": "User Uncaught Exceptions", "default": True, "description": "Break when exception escapes into library code."}),
				]
			})

		if command == 'disconnect':
			self.dispose()

			for connection in self.connections:
				await connection

			return {}

		return {}

	def on_transport_closed(self) -> Any: ...

	def write(self, message: bytes):
		raise NotImplemented()

	def readline(self) -> bytes:
		raise NotImplemented()

	def read(self, n: int) -> bytes:
		raise NotImplemented()

	def dispose(self):
		self.process.dispose()
		self.socket.close()

		for client in self.clients:
			client.close()
