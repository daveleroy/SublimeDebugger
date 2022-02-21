from __future__ import annotations

from typing import Any, Callable

import sublime

class SettingsMeta(type):
	def __getattribute__(self, key: str) -> Any:
		return SettingsRegistery.settings.get(key)

	def __setattr__(self, key: str, value: Any) -> None:
		SettingsRegistery.settings.set(key, value)
		sublime.save_settings('debugger.sublime-settings')

class Settings(metaclass=SettingsMeta):
	open_at_startup: bool = True
	ui_scale: int = 10

	ui_rem_width_scale: float = 1
	ui_rem_width_scale_adjust_automatically: bool = False

	font_face: str = 'Monospace'

	external_terminal: str = "terminus"
	hide_status_bar: bool = False
	keep_panel_open: bool = False
	bring_window_to_front_on_pause: bool = False

	development: bool = False

	log_info: bool = False
	log_exceptions: bool = True
	log_errors: bool = True

	console_layout_begin: Any = []
	console_layout_end: Any = []
	console_layout_focus: Any = []

	node: str|None = None

	go_dlv: str|None = None

	lldb_show_disassembly: str = "auto"
	lldb_display_format: str = "auto"
	lldb_dereference_pointers: bool = True
	lldb_library: str|None = None
	lldb_python: str|None = None


class SettingsRegistery:
	settings: sublime.Settings

	@staticmethod
	def initialize(on_updated: Callable[[], None]):
		SettingsRegistery.settings = sublime.load_settings('debugger.sublime-settings')
		SettingsRegistery.settings.clear_on_change('debugger_settings')
		SettingsRegistery.settings.add_on_change('debugger_settings', on_updated)

	@staticmethod
	def save():
		sublime.save_settings('debugger.sublime-settings')

