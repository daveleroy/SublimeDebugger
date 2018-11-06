from sublime_db.core.typecheck import List, Optional, Generator, Any, Callable, Dict

import sublime
import json
import re
from sublime_db import core
from .adapter_configuration import AdapterConfiguration
from .util import get_setting

class Configuration:
	def __init__(self, name: str, type: str, request: str, all: dict) -> None:
		self.name = name
		self.type = type
		self.all = all
		self.index = -1
		self.request = request

	@staticmethod
	def from_json(json: dict) -> None:
		name = json.get('name')
		assert name, 'expecting name for debug.configuration'
		type = json.get('type')
		assert type, 'expecting type for debug.configuration'
		request = json.get('request')
		assert request, 'expecting request for debug.configuration'
		return Configuration(name, type, request, json)


@core.async
def add_configuration (window: sublime.Window, adapters: Dict[str, AdapterConfiguration]) -> core.awaitable[None]:
	names = []
	content = []
	for name, adapter in adapters.items():	
		snippets = adapter.snippets
		for snippet in adapter.snippets:
			names.append(snippet.get('label', 'label'))
			content.append(snippet.get('body', '{ snippet error: no body field}'))

	names.append('Other: Custom')

	index = yield from core.sublime_show_quick_panel_async(window, names, 0)
	if index < 0:
		return

	if index >= len(content):
		yield from insert_snippet(window, {'name': 'NAME', 'type' : 'CUSTOM', 'request' : 'attach'})
	else:
		yield from insert_snippet(window, content[index])

	
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
			'characters' : '\n'
		})
		view.run_command('insert_snippet', {
			'contents' : content + ','
		})
	else:	
		sublime.set_clipboard(content)
		core.display('Snippet copied to clipboard')

def show_settings(window: sublime.Window) -> None:
	sublime.active_window().run_command('edit_settings', {
		"base_file" : "${packages}/sublime_db/debug.sublime-settings"
	})

@core.async
def select_or_add_configuration(window: sublime.Window, index: Optional[int], configurations: List[Configuration], adapters: List[AdapterConfiguration]) -> core.awaitable[Optional[Configuration]]:
	done = core.main_loop.create_future()
	names = []
	for c in configurations:
		if index is not None and c.index == index:
			names.append(c.name + ' ✓')
		else:
			names.append(c.name)

	names.append("-- Add Configuration -- ")

	index = yield from core.sublime_show_quick_panel_async(window, names, index or 0)
	if index < 0:
		return None
	if index >= len(configurations):
		yield from add_configuration(window, adapters)
		return None
	return configurations[index]
