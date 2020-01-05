
from ...typecheck import *
from ...import core
from ...import ui

from .adapter import Adapter
from .configuration import Configuration

import sublime
import json

if TYPE_CHECKING:
	from ..debugger import Debugger

def insert_snippet(window: sublime.Window, snippet: dict) -> core.awaitable[None]:
	content = json.dumps(snippet, indent="\t")
	content = content.replace('\\\\', '\\') # remove json encoded \ ...
	project = window.project_file_name()
	if project:
		view = yield from core.sublime_open_file_async(window, project)
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


def add_configuration(adapters: Dict[str, Adapter]):
	def insert_custom():
		core.run(insert_snippet(sublime.active_window(), {
				'name': '<NAME>',
				'type': '<CUSTOM>',
				'request': 'launch|attach'
			}))

	values = [
		ui.InputListItem(insert_custom, 'Create Custom Configuration')
	]

	for name, adapter in adapters.items():
		snippets = adapter.snippets
		for snippet in adapter.snippets:
			def insert(snippet=snippet):
				insert = snippet.get('body', '{ error: no body field}')
				core.run(insert_snippet(sublime.active_window(), insert))

			values.append(ui.InputListItem(insert, snippet.get('label', 'label')))

	return ui.InputList(values, placeholder="choose a configuration type")



def select_configuration(debugger: 'Debugger'):
	values = []
	for c in debugger.configurations:
		values.append(ui.InputListItemChecked(lambda c=c: debugger.changeConfiguration(c), c.name, c.name, c == debugger.configuration)) #type: ignore

	values.append(ui.InputListItem(add_configuration(debugger.adapters), "Add Configuration"))

	return ui.InputList(values, "Add or Select Configuration")
