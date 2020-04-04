from ..typecheck import *
from ..import core
from ..import ui

import sublime
import re

def get_setting(view: Optional[sublime.View], setting: str, default: Any = None) -> Any:
	plugin_settings = sublime.load_settings('debugger.sublime-settings')
	plugin_setting = plugin_settings.get(setting, default)
	if not view:
		return plugin_setting

	project_setting = view.settings().get("debug." + setting, plugin_setting)
	return project_setting

def get_debugger_setting(setting: str, default: Any = None) -> Any:
	plugin_settings = sublime.load_settings('debugger.sublime-settings')
	return plugin_settings.get(setting, default)

