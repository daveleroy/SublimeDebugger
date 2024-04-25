from __future__ import annotations
from typing import Any

from .import util
from .. import dap
from .. import core

import sublime
import os
import shutil

initial_preferences = '''{
	"theme": "Debugger.sublime-theme"
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

	async def installable_versions(self, log: core.Logger) -> list[str]:
		version = await util.request.text('https://download.sublimetext.com/latest/dev')
		return ['4143', version.strip(), sublime.version()]

	def installed_version(self):
		try:
			path = f'{self.install_path()}/package.json'
			with open(path) as file:
				return core.json_decode(file.read())['version']
		except:
			...

		return None

	async def install(self, version: str | None, log: core.Logger) -> None:
		platform = sublime.platform()
		arch = sublime.arch()

		path = self.temporary_install_path()
		path_app = f'{path}/{self.debug_app_name}'

		if platform == 'osx':
			await util.request.download_and_extract_zip(f'https://download.sublimetext.com/sublime_text_build_{version}_mac.zip', path_app, log=log)
		elif platform == 'windows' and arch =='x64':
			await util.request.download_and_extract_zip(f'https://download.sublimetext.com/sublime_text_build_{version}_x64.zip', path_app, log=log)
		else:
			raise core.Error('Install for this platform/arch is not currently supported')


		# The windows version has a data folder already here here
		core.remove_file_or_dir(f'{path_app}/Data')

		await util.request.download_and_extract_zip('https://github.com/microsoft/debugpy/archive/refs/tags/v1.7.0.zip', f'{path}/debugpy', log=log)
		await util.request.download_and_extract_zip('https://github.com/daveleroy/debugpy/archive/refs/tags/v1.5.1.zip', f'{path}/debugpy_for_3.3', log=log)

		core.write(f'{path}/package.json', core.json_encode({
			'version': version
		}))

	@property
	def debug_app_name(self):
		platform = sublime.platform()
		if platform == 'osx':
			return 'Sublime Text (Debug).app'
		else:
			return 'Sublime Text (Debug)'


class Sublime(dap.AdapterConfiguration):

	type = 'sublime'
	docs = 'https://github.com/microsoft/vscode-docs/blob/main/docs/python/debugging.md#python-debug-configurations-in-visual-studio-code'
	installer = SublimeInstaller()
	development = True

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		if configuration.request == 'attach':
			command = [
				configuration['python'],
				f'{self.installer.install_path()}/debugpy/src/debugpy/adapter',
			]
			return dap.StdioTransport(command)

		python = configuration.get('python') or shutil.which('python3') or shutil.which('python')
		if not python:
			raise core.Error('Unable to find `python3` or `python`')

		configuration['python'] = python
		configuration['port_33'] =  configuration.get('port_33') or util.get_open_port()
		configuration['port_38'] =  configuration.get('port_38') or util.get_open_port()

		log.info('Using python `{}`'.format(python))
		return SublimeDebugTransport(configuration, log)

	async def on_custom_event(self, session: dap.Session, event: str, body: Any):
		if event == 'attach':
			configuration = dap.Configuration.from_json(body, -1)
			configuration_expanded = dap.ConfigurationExpanded(configuration, session.configuration.variables)
			await session.debugger.launch(session.breakpoints, self, configuration_expanded, parent=session)

	def on_saved_source_file(self, session: dap.Session, file: str):
		if entry := session.configuration.get('entry'):
			print('reload', 'on_saved_source_file')
			for child in session.children:
				core.run(child.request('reload', {
					'entry': entry,
					'file': file,
				}))

	@property
	def configuration_snippets(self):
		keys = {
			'osx': 'OSX',
			'windows': 'Windows',
			'linux': 'Linux',
		}
		platform_key = keys[sublime.platform()]

		return [{
			'label': 'Sublime Plugin Debug',
			'body': {
				'name': 'Sublime Plugin Debug',
				'type': 'sublime',
				'request': 'launch',
				'entry': '${1:Package}.plugin',
				'args': [
					'${project_path}'
				],
				'linked_packages': [
					'${1:Package}',
					'User/Preferences.sublime-settings',
					f'User/Default ({platform_key}).sublime-keymap',
				]
			}
		}]

	@property
	def configuration_schema(self):
		return {
			'launch': {
				'required': [
					'linked_packages'
				],
				'properties': {
					'entry': {
						'type': 'string',
						'description': 'Module entry point used for reloading the package using `sublime_plugin.reload` when a save occurs.',
					},
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





class SublimeDebugTransport(dap.Transport):
	def __init__(self, configuration: dap.ConfigurationExpanded, log: core.Logger) -> None:
		super().__init__()

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
		core.symlink(f'{adapters_path}/sublime_adapter_runtime.py', f'{data_directory}/Lib/Python33/sublime_adapter_runtime.py')
		core.symlink(f'{adapters_path}/sublime_adapter_runtime.py', f'{data_directory}/Lib/Python38/sublime_adapter_runtime.py')


		# Add plugin that initializes the sublime_debug_runtime module before any other packages so it can attach debugpy before any other user packages get loaded
		core.make_directory(f'{data_directory}/Packages/0_sublime_adapter_runtime_38')
		core.write(f'{packages_directory}/0_sublime_adapter_runtime_38/__init__.py', 'import sublime_adapter_runtime', overwrite_existing=True)
		core.write(f'{packages_directory}/0_sublime_adapter_runtime_38/.python-version', '3.8', overwrite_existing=True)

		core.make_directory(f'{data_directory}/Packages/0_sublime_adapter_runtime_33')
		core.write(f'{packages_directory}/0_sublime_adapter_runtime_33/__init__.py', 'import sublime_adapter_runtime', overwrite_existing=True)
		core.write(f'{packages_directory}/0_sublime_adapter_runtime_33/.python-version', '3.3', overwrite_existing=True)


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
				'remoteRoot': f'{packages_directory}/{name}',
				'localRoot': package,
			})


		core.write(f'{packages_directory}/User/Preferences.sublime-settings', initial_preferences)

		settings = sublime.load_settings('Preferences.sublime-settings')
		core.write(f'{packages_directory}/User/Debugger.sublime-theme', theme.format(settings.get("theme")), overwrite_existing=True)

		commands = [f'{sublime_text_directory}/sublime_text', '--multiinstance']
		commands.extend(configuration.get('args', []))

		self.log = log
		self.path_mappings = path_mappings

		env = {
			'sublime_debug_configuration': core.json_encode(configuration)
		}
		env.update(os.environ)

		log.info('Starting `Sublime Text (Debug)`')
		self.process = dap.Process(commands, env=env)
		self.process.on_stdout(self.read, lambda: self.close())

	def read(self, output: str):
		self.log.info(output)

	def close(self):
		self.process.dispose()
		self.events.on_event('terminated', core.JSON())

	async def start(self, listener: dap.TransportListener, configuration: dap.ConfigurationExpanded, log: core.Logger):
		self.events = listener
		self.log = log

		self.events.on_event('attach', core.JSON({
			'type': 'sublime',
			'request': 'attach',
			'name': 'plugin_host_38',
			'listen': {
				'host': 'localhost',
				'port': configuration['port_38'],
			},
			'python': configuration['python'],
			'justMyCode': False,
			'redirectOutput': True,
			'pathMappings': self.path_mappings,
		}))


		self.events.on_event('attach', core.JSON({
			'type': 'sublime',
			'request': 'attach',
			'name': 'plugin_host_33',
			'listen': {
				'host': 'localhost',
				'port': configuration['port_33'],
			},
			'python': configuration['python'],
			'justMyCode': False,
			'redirectOutput': True,
			'pathMappings': self.path_mappings,
		}))

	async def initialized(self):
		self.events.on_event('initialized', core.JSON({}))

	# TODO: Respond to more requests so this actually implements the protocol correctly
	async def send_request(self, command: str, args: core.JSON|None) -> core.JSON:
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
			if not self.process.closed:
				self.log.warn('Consider ending the debug session by quitting `Sublime Text (Debug)`')
				self.log.warn('Disconnecting via the stop button is not recommended since the Sublime session may not be saved thus any changes to the window size etc will be lost')

			self.dispose()
			return core.JSON()

		return core.JSON()

	def dispose(self):
		self.process.dispose()
