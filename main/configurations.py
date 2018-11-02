from sublime_db.core.typecheck import List, Optional, Generator, Any, Callable, Dict

import sublime
import json
import re
from sublime_db import core
from .adapter_configuration import AdapterConfiguration

class SettingsChangedCallbabck:
	id = 0
	def __init__(self, settings: List[sublime.Settings], on_changed: Callable[[], None]) -> None:
		SettingsChangedCallbabck.id += 1
		self.settings = settings
		self.key = 'SettingsChangedCallbabck{}'.format(SettingsChangedCallbabck.id)
		for setting in settings:
			setting.add_on_change(self.key, on_changed)

	def dispose (self) -> None:
		for setting in self.settings:
			setting.clear_on_change(self.key)

def register_on_changed_setting(view: sublime.View, on_changed: Callable[[], None]) -> SettingsChangedCallbabck:
	plugin_settings = sublime.load_settings('debug.sublime-settings')
	view_settings = view.settings()
	return SettingsChangedCallbabck([plugin_settings, view_settings], on_changed)

def get_setting(view: Optional[sublime.View], setting: str, default: Any = None) -> Any:
	plugin_settings = sublime.load_settings('debug.sublime-settings')
	plugin_setting = plugin_settings.get(setting, default)
	if not view:
		return plugin_setting

	project_setting = view.settings().get("debug." + setting, plugin_setting)
	return project_setting

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


def all_configurations (window: sublime.Window) -> List[Configuration]:
	configs = get_setting(window.active_view(), 'configurations', [])
	configurations = []
	for index, config in enumerate(configs):
		configuration = Configuration.from_json(config)
		configuration.index = index
		configurations.append(configuration)
	return configurations

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
def select_configuration(window: sublime.Window, index: int, adapters: List[AdapterConfiguration]) -> core.awaitable[Optional[Configuration]]:
	try:
		configs = all_configurations(window)
	except Exception as e:
		core.display(e)
		show_settings(window)
		
	done = core.main_loop.create_future()
	names = list(map(lambda x: x.name, configs)) + ["-"] +  ["Add Configuration"]

	index = yield from core.sublime_show_quick_panel_async(window, names, index)
	if index < 0:
		return None
	if index >= len(configs):
		yield from add_configuration(window, adapters)
		return None
	return configs[index]

# since configurations are in an array and we allow duplicate names like vs code 
# we use the combination of index + name to attempt to find the correct configuration
def get_configuration_for_name(window: sublime.Window, name: str, index: Optional[int]) -> Optional[Configuration]:
	configs = all_configurations(window)
	if index:
		try:
			config_at_index = configs[index]
			if config_at_index.name == name:
				return config_at_index
		except IndexError:
			pass

	for config in configs:
		if config.name == name:
			return config

	return None