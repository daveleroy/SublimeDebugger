from sublime_db.core.typecheck import (
	List, 
	Callable,
	Optional,
	Any
)

import sublime

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