from __future__ import annotations
from .typecheck import *

from .import core
from .import ui
from .import dap
from .settings import Settings

import sublime
import json
import functools


class AdaptersRegistry:
	all: ClassVar[list[dap.AdapterConfiguration]] = []
	types: ClassVar[dict[str, dap.AdapterConfiguration]] = {}

	@staticmethod
	def initialize():
		def subclasses(cls=dap.AdapterConfiguration):
			all_subclasses = []
			for subclass in cls.__subclasses__():
				all_subclasses.append(subclass)
				all_subclasses.extend(subclasses(subclass))
			return all_subclasses

		# create and register all the adapters
		for klass in subclasses():
			AdaptersRegistry.register(klass())

	@staticmethod
	def register(adapter: dap.AdapterConfiguration):
		AdaptersRegistry.all.append(adapter)
		
		AdaptersRegistry.types[adapter.type] = adapter
		for type in adapter.types:
			AdaptersRegistry.types[type] = adapter

	@staticmethod
	def get(type: str) -> dap.AdapterConfiguration:
		if adapter := AdaptersRegistry.types.get(type):
			return adapter

		raise core.Error(f'Unable to find debug adapter with the type name "{type}"')

	@staticmethod
	async def install(type: str, log: core.Logger):
		try:
			await AdaptersRegistry.get(type).install(log)

		except Exception as error:
			log.error(f'Failed to install adapter: {str(error)}')
			raise error

		log.info('Successfully Installed Adapter!')

		AdaptersRegistry.recalculate_schema()

	@staticmethod
	async def install_list_items(show_configurations: bool = True, check_status: bool = True, log: core.Logger = core.stdio):

		def insert_custom(type: str, request: str):
			core.run(AdaptersRegistry._insert_snippet(sublime.active_window(), {
				'name': f'Debug {type}',
				'type': type,
				'request': request,
			}))

		def insert(snippet: Any):
			insert = snippet.get('body', '{ error: no body field }')
			core.run(AdaptersRegistry._insert_snippet(sublime.active_window(), insert))

		def install(adapter: dap.AdapterConfiguration):
			core.run(AdaptersRegistry.install(adapter.type, log))

		installed: list[Awaitable[ui.InputListItem]] = []
		not_installed: list[Awaitable[ui.InputListItem]] = []

		for adapter in AdaptersRegistry.all:
			if not Settings.development and adapter.development:
				continue

			async def item(adapter: dap.AdapterConfiguration) -> ui.InputListItem:
				name = adapter.type
				installed_version = adapter.installed_version

				if adapter.development:
					name += '\tdev'

				if check_status and installed_version:
					name += '\t'
					try:
						status = await adapter.installed_status(log)
						if status:
							name += f'{status}\t\t'

					except Exception as e:
						name += f'Failed to fetch status {e}\t\t'

					name += f'{installed_version}'

				elif installed_version:
					name += '\t'
					name += f'{installed_version}'
				elif check_status:
					status = await adapter.installed_status(log)
					if status:
						name += '\t'
						name += f'{status}'

				if installed_version and not show_configurations:
					snippet_input_items: list[ui.InputListItem] = []

					for snippet in adapter.configuration_snippets or []:
						type = snippet.get('body', {}).get('request', '??')
						snippet_input_items.append(ui.InputListItem(functools.partial(insert, snippet), snippet.get('label', 'label'), details=type))

					if not snippet_input_items:
						snippet_input_items.append(ui.InputListItem(functools.partial(insert_custom, adapter.type, 'launch'), 'Default Launch', details='configuration snippet'))
						snippet_input_items.append(ui.InputListItem(functools.partial(insert_custom, adapter.type, 'attach'), 'DefaultAttach', details='configuration snippet'))
						subtitle = '2 Snippets\t'

					else:
						subtitle = f'{len(snippet_input_items)} Snippets' if len(snippet_input_items) != 1 else '1 Snippet'


					snippet_input_items.append(ui.InputListItem(functools.partial(install, adapter), 'Reinstall', details=[' ']))

					return ui.InputListItemChecked(
						ui.InputList(snippet_input_items, 'choose a snippet to insert'),
						installed_version != None,
						name,
						details=f'{subtitle} <a href="{adapter.docs}">documentation</a>'
					)
				elif installed_version:
					return ui.InputListItemChecked(
						functools.partial(install, adapter),
						installed_version != None,
						name,
						details=f'Reinstall\t<a href="{adapter.docs}">documentation</a>'
					)
				else:
					return ui.InputListItemChecked(
						functools.partial(install, adapter),
						installed_version != None,
						name,
						details=f'Not Installed\t<a href="{adapter.docs}">documentation</a>'
					)

			if adapter.installed_version:
				installed.append(item(adapter))
			else:
				not_installed.append(item(adapter))
			
		items = list(await core.gather(*(installed + not_installed)))
		return items

	@staticmethod
	async def install_menu(log: core.Logger = core.stdio):
		items = await AdaptersRegistry.install_list_items(check_status=True, log=log)
		return ui.InputList(items, 'Install/Update Debug Adapters')

	@staticmethod
	async def _insert_snippet(window: sublime.Window, snippet: dict[str, Any]):
		for (key, value) in snippet.items():
			if isinstance(value, str) and value.startswith('^"') and value.endswith('"'):
				snippet[key] = value[2:-1]

		content = json.dumps(snippet, indent="\t")
		content = content.replace('\\\\', '\\') # remove json encoded \ ...
		content = content.replace('${workspaceFolder}', '${folder}')

		try:

			project = window.project_file_name()
			if not project:
				raise core.Error('Expected project file in window')

			view = await core.sublime_open_file_async(window, project)
			region = view.find(r'''"\s*debugger_configurations\s*"\s*:\s*\[''', 0)
			if not region:
				raise core.Error('Unable to find debugger_configurations')

			view.sel().clear()
			view.sel().add(sublime.Region(region.b, region.b))
			view.run_command('insert', {
				'characters': '\n'
			})
			view.run_command('insert_snippet', {
				'contents': content + ','
			})
		except core.Error as e:
			sublime.set_clipboard(content)
			core.display('Unable to insert configuration into sublime-project file: Copied to clipboard instead')

	@staticmethod
	async def add_configuration(log: core.Logger = core.stdio):
		items = await AdaptersRegistry.install_list_items(show_configurations=False, check_status=False, log=log)
		return ui.InputList(items, 'Add Debug Configuration')

	@staticmethod
	def recalculate_schema():
		from .schema import save_schema
		save_schema(AdaptersRegistry.all)
