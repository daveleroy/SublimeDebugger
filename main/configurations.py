from sublime_db.core.typecheck import List, Optional, Generator, Any

import sublime

from sublime_db import core

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

def _get_configurations(configs: list) -> List[Configuration]:
	r = []
	for config in configs:
		name = config.get('name')
		assert name, 'expecting name for debug.configuration'
		type = config.get('type')
		assert type, 'expecting type for debug.configuration'
		request = config.get('request')
		assert request, 'expecting request for debug.configuration'
		c = Configuration(name, type, request, config)
		r.append(c)
	return r

def _project_configurations(window: sublime.Window) -> List[Configuration]:
	configs = get_setting(window.active_view(), 'configurations')
	if not configs:
		return []

	assert isinstance(configs, list), 'expected [] for debug.configurations'
	return _get_configurations(configs)


def all_configurations (window: sublime.Window) -> List[Configuration]:
	configurations = _project_configurations(window)
	for index, config in enumerate(configurations):
		config.index = index
	return configurations

def show_settings(window: sublime.Window) -> None:
	sublime.active_window().run_command('edit_settings', {
		"base_file" : "${packages}/sublime_db/debug.sublime-settings"
	})

@core.async
def select_configuration(window: sublime.Window, index: int) -> core.awaitable[Optional[Configuration]]:
	try:
		configs = all_configurations(window)
	except Exception as e:
		core.display(e)
		show_settings(window)
		
	done = core.main_loop.create_future()
	names = list(map(lambda x: x.name, configs)) + ["-"] +  ["Add configuration"]

	index = yield from core.sublime_show_quick_panel_async(window, names, index)
	if index < 0:
		return None
	if index >= len(configs):
		project = window.project_file_name()
		if project:
			sublime.run_command("new_window")
			window = sublime.active_window()
			window.open_file(project)
		else:				
			window.run_command('edit_settings', {
				"base_file" : "${packages}/sublime_db/debug.sublime-settings"
			})
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