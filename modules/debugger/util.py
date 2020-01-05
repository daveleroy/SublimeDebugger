from ..typecheck import *
from ..import core
from ..import ui

import sublime
import re


class SettingsChangedCallbabck:
	id = 0

	def __init__(self, settings: List[sublime.Settings], on_changed: Callable[[], None]) -> None:
		SettingsChangedCallbabck.id += 1
		self.settings = settings
		self.key = 'SettingsChangedCallbabck{}'.format(SettingsChangedCallbabck.id)
		for setting in settings:
			setting.add_on_change(self.key, on_changed)

	def dispose(self) -> None:
		for setting in self.settings:
			setting.clear_on_change(self.key)


class WindowSettingsCallback:
	def __init__(self, window: sublime.Window, on_changed: Callable[[], None]):
		self.window = window
		self.settings_changed_callback = None #type: Optional[SettingsChangedCallbabck]
		self.on_changed = on_changed
		self.on_view_updated = ui.view_activated.add(self.on_update_settings_view)
		
		view = window.active_view()
		if view:
			self.update(view)

	def on_update_settings_view(self, view: sublime.View):
		if view.window() == self.window:
			self.update(view)

	def update(self, view: sublime.View):
		core.log_info("updating settings callback view")
		if self.settings_changed_callback:
			self.settings_changed_callback.dispose()
			self.settings_changed_callback = None

		plugin_settings = sublime.load_settings('debugger.sublime-settings')
		view_settings = view.settings()
		self.settings_changed_callback = SettingsChangedCallbabck([plugin_settings, view_settings], self.on_changed)

	def dispose(self):
		self.on_view_updated.dispose()
		if self.settings_changed_callback:
			self.settings_changed_callback.dispose()
			self.settings_changed_callback = None


def get_setting(view: Optional[sublime.View], setting: str, default: Any = None) -> Any:
	plugin_settings = sublime.load_settings('debugger.sublime-settings')
	plugin_setting = plugin_settings.get(setting, default)
	if not view:
		return plugin_setting

	project_setting = view.settings().get("debug." + setting, plugin_setting)
	return project_setting
