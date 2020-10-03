from ...typecheck import *
from ...import core
from ...import ui

from ..dap import AdapterConfiguration

import sublime
import json

class Adapters:
	all: ClassVar[List[AdapterConfiguration]]

	@staticmethod
	def initialize():
		Adapters.all = [klass() for klass in AdapterConfiguration.__subclasses__()]

	@staticmethod
	def get(type: str) -> AdapterConfiguration:
		for adapter in Adapters.all:
			if type == adapter.type:
				return adapter

		raise core.Error(f'Unable to find debug adapter with the type name "{type}"')

	@staticmethod
	def install_menu(log: core.Logger = core.stdio):
		items = []
		for adapter in Adapters.all:
			name = adapter.type
			installed_version = adapter.installed_version
			if installed_version:
				name += '\t'
				name += str(installed_version)

			items.append(
				ui.InputListItemChecked(
					lambda adapter=adapter: core.run(adapter.install(log)), #type: ignore
					name,
					name,
					installed_version != None
				)
			)
		return ui.InputList(items, "Install Debug Adapters")

	@staticmethod
	async def _insert_snippet(window: sublime.Window, snippet: dict):
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
			core.run(Adapters._insert_snippet(sublime.active_window(), {
					'name': f'Debug {type}',
					'type': type,
					'request': request,
				}))

		values = []

		for adapter in Adapters.all:
			if not adapter.installed_version:
				continue

			snippet_input_items = []

			for snippet in adapter.configuration_snippets or []:
				def insert(snippet=snippet):
					insert = snippet.get('body', '{ error: no body field}')
					core.run(Adapters._insert_snippet(sublime.active_window(), insert))

				snippet_input_items.append(ui.InputListItem(insert, snippet.get('label', 'label')))

			if not snippet_input_items:
				snippet_input_items.append(ui.InputListItem(lambda adapter=adapter: insert_custom(adapter.type, "launch"), 'Launch'))
				snippet_input_items.append(ui.InputListItem(lambda adapter=adapter: insert_custom(adapter.type, "attach"), 'Attach'))

			values.append(ui.InputListItem(ui.InputList(snippet_input_items, "choose a snippet to insert"), adapter.type))

		return ui.InputList(values, placeholder="choose a configuration type")

	@staticmethod
	def recalculate_schema():
		from .schema import save_schema
		save_schema(Adapters.all)
