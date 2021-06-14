from __future__ import annotations
from .typecheck import *

from .import core
from .import ui
from .import dap

import sublime
import json
import asyncio

class AdaptersRegistry:
	all: ClassVar[list[dap.AdapterConfiguration]]

	@staticmethod
	def initialize():
		AdaptersRegistry.all = [klass() for klass in dap.AdapterConfiguration.__subclasses__()]

	@staticmethod
	def get(type: str) -> dap.AdapterConfiguration:
		for adapter in AdaptersRegistry.all:
			if type == adapter.type:
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
	async def install_menu(check_status: bool = True, log: core.Logger = core.stdio):
		items: list[Awaitable[ui.InputListItem]] = []

		for adapter in AdaptersRegistry.all:
			async def item(adapter: dap.AdapterConfiguration) -> ui.InputListItem:
				name = adapter.type
				installed_version = adapter.installed_version

				details: list[str] = []

				if check_status and installed_version:
					name += '\t'
					try:
						status = await adapter.installed_status(log)
						if status:
							name += f'{status}\t\t'

					except Exception as e:
						name += f'Failed to fetch status {e}\t\t'

					name += f'{installed_version}'

				if adapter.docs:
					details.append(f'<a href="{adapter.docs}">documentation</a>')

				return ui.InputListItemChecked(
					lambda adapter=adapter: core.run(AdaptersRegistry.install(adapter.type, log)), #type: ignore
					name,
					name,
					installed_version != None,
					details=details
				)

			items.append(item(adapter))
		
		return ui.InputList(list(await asyncio.gather(*items)), 'Install Debug Adapters')

	@staticmethod
	async def _insert_snippet(window: sublime.Window, snippet: dict[str, Any]):
		content = json.dumps(snippet, indent="\t")
		content = content.replace('\\\\', '\\') # remove json encoded \ ...
		project = window.project_file_name()
		if project:
			view = await core.sublime_open_file_async(window, project)
			region = view.find(r'''"\s*debugger_configurations\s*"\s*:\s*\[''', 0)
			view.sel().clear()
			view.sel().add(sublime.Region(region.b, region.b))
			view.run_command('insert', {
				'characters': '\n'
			})
			view.run_command('insert_snippet', {
				'contents': content + ','
			})
		else:
			sublime.set_clipboard(content)
			core.display('Unable to insert configuration into sublime-project file: Copied to clipboard instead')

	@staticmethod
	def add_configuration():
		def insert_custom(type: str, request: str):
			core.run(AdaptersRegistry._insert_snippet(sublime.active_window(), {
				'name': f'Debug {type}',
				'type': type,
				'request': request,
			}))

		values: list[ui.InputListItem] = []

		for adapter in AdaptersRegistry.all:
			if not adapter.installed_version:
				continue

			snippet_input_items: list[ui.InputListItem] = []

			for snippet in adapter.configuration_snippets or []:
				def insert(snippet=snippet):
					insert = snippet.get('body', '{ error: no body field}')
					core.run(AdaptersRegistry._insert_snippet(sublime.active_window(), insert))

				snippet_input_items.append(ui.InputListItem(insert, snippet.get('label', 'label'), kind = sublime.KIND_SNIPPET))

			if not snippet_input_items:
				snippet_input_items.append(ui.InputListItem(lambda adapter=adapter: insert_custom(adapter.type, 'launch'), 'Launch', kind = sublime.KIND_SNIPPET))
				snippet_input_items.append(ui.InputListItem(lambda adapter=adapter: insert_custom(adapter.type, 'attach'), 'Attach', kind = sublime.KIND_SNIPPET))
				subtitle = 'Default Snippets'

			else:
				subtitle = f'{len(snippet_input_items)} Snippets' if len(snippet_input_items) != 1 else '1 Snippet'

			values.append(ui.InputListItem(ui.InputList(snippet_input_items, 'choose a snippet to insert'), adapter.type, annotation = subtitle, kind = sublime.KIND_SNIPPET))

		return ui.InputList(values, placeholder='choose a configuration type')

	@staticmethod
	def recalculate_schema():
		from .adapters.adapter.schema import save_schema
		save_schema(AdaptersRegistry.all)
