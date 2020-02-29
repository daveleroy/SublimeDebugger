from ...typecheck import *
from ...import core
from ...import ui

import sublime
import json

class Adapter (Protocol):
	@property
	def type(self): ...
	async def start(self, log: core.Logger): ...

	@property
	def version(self) -> Optional[str]: ...

	@property
	def configuration_snippets(self) -> Optional[list]: ...

	@property
	def configuration_shema(self) -> Optional[dict]: ...

	@property
	def is_installed(self) -> bool: ...

	async def install(self, log: core.Logger): ...

	def on_hover_provider(self, view: sublime.View, point: int) -> Optional[str]:
		word = view.word(point)
		word_string = word and view.substr(word)
		if word_string:
			return (word_string, word)
		return None

class Adapters:
	all: ClassVar[List[Adapter]]

	@staticmethod
	def initialize():
		Adapters.all = [klass() for klass in Adapter.__subclasses__()]

	@staticmethod
	def get(type: str) -> Adapter:
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
			region = view.find('''"\s*debug.configurations\s*"\s*:\s*\[''', 0)
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
					'name': 'request',
					'type': 'type',
					'request': 'launch|attach',
					'<MORE>': '...'
				}))

		values = [
			ui.InputListItem(insert_custom, 'Create Custom Configuration')
		]

		for adapter in Adapters.all:
			snippet_input_items = []

			for snippet in adapter.configuration_snippets or []:
				def insert(snippet=snippet):
					insert = snippet.get('body', '{ error: no body field}')
					core.run(Adapters._insert_snippet(sublime.active_window(), insert))

				snippet_input_items.append(ui.InputListItem(insert, snippet.get('label', 'label')))
			
			if not snippet_input_items:
				snippet_input_items.append(ui.InputListItem(lambda: insert_custom(adapter.type, "launch"), 'launch'))
				snippet_input_items.append(ui.InputListItem(lambda: insert_custom(adapter.type, "attach"), 'attach'))

			values.append(ui.InputListItem(ui.InputList(snippet_input_items, "choose a snippet to insert"), adapter.type))

		return ui.InputList(values, placeholder="choose a configuration type")


	@staticmethod
	def select_configuration(debugger: 'Debugger'):
		values = []
		for c in debugger.configurations:
			values.append(ui.InputListItemChecked(lambda c=c: debugger.changeConfiguration(c), c.name, c.name, c == debugger.configuration)) #type: ignore

		values.append(ui.InputListItem(Adapters.add_configuration(), "Add Configuration"))

		return ui.InputList(values, "Add or Select Configuration")

	@staticmethod
	def recalculate_schema():
		from .schema import save_schema
		save_schema(Adapters.all)
