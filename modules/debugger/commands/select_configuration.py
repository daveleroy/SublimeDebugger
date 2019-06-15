from sublime_db.modules.core.typecheck import (
	Any,
	Callable,
	Optional,
	Dict,
	TYPE_CHECKING
)
if TYPE_CHECKING:
	from sublime_db.modules.debugger.debugger_interface import DebuggerInterface

import sublime
import sublime_plugin
import json

from sublime_db.modules import core
from sublime_db.modules import ui
from sublime_db.modules.debugger_stateful.adapter_configuration import AdapterConfiguration, Configuration


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


def add_configuration(adapters: Dict[str, AdapterConfiguration]):
	values = []
	content = []
	for name, adapter in adapters.items():
		snippets = adapter.snippets
		for snippet in adapter.snippets:
			values.append(ui.ListInputItem(snippet.get('label', 'label')))
			content.append(snippet.get('body', '{ snippet error: no body field}'))

	values.append(ui.ListInputItem('Other: Custom'))
	input = ui.ListInput(values, placeholder="choose a configuration type", index=0)

	def run(list):
		index = list
		if index >= len(content):
			core.run(insert_snippet(sublime.active_window(), {'name': 'NAME', 'type': 'CUSTOM', 'request': 'attach'}))
		else:
			core.run(insert_snippet(sublime.active_window(), content[index]))

	ui.run_input_command(input, run)


def run(debugger: 'DebuggerInterface') -> core.awaitable[Optional[Configuration]]:
	#done = core.create_future()
	values = []
	for c in debugger.configurations:
		if c == debugger.configuration:
			values.append(ui.ListInputItem("● {}".format(c.name)))
		else:
			values.append(ui.ListInputItem("○ {}".format(c.name)))

	
	values.append(ui.ListInputItem("Add new configuration"))
	input = ui.ListInput(values, placeholder="add or select configuration", index=0)

	def run(list):
		index = list
		if index < len(debugger.configurations):
			debugger.changeConfiguration(debugger.configurations[index])
		else:
			add_configuration(debugger.adapters)

	ui.run_input_command(input, run)

