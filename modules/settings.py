from __future__ import annotations

from typing import Any, Callable

import sublime
from .import core

class Settings:
	open_at_startup: bool = True
	ui_scale: int = 10
	ui_estimated_width_scale: int = 1

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
	@staticmethod
	def initialize_class(Class, settings):
		core.debug('--', Class.__name__, '--')

		for variable_name in vars(Class):
			if variable_name.startswith('_'): continue
			core.debug('setting:', variable_name)

			if variable_name == 'initialize': continue
			if variable_name == 'save': continue

			key = variable_name

			class Set:
				def __init__(self, key: str):
					self.key = key

				def __get__(self, obj: Any, objtype: Any):
					return settings.get(self.key)

				def __set__(self, obj: Any, val: Any):
					settings.set(self.key, val)
					sublime.save_settings('debugger.sublime-settings')

			s = Set(key)
			setattr(Class, variable_name, s)

	@staticmethod
	def initialize(on_updated: Callable[[], None]):
		settings = sublime.load_settings('debugger.sublime-settings')
		settings.add_on_change('debugger_settings', on_updated)

		SettingsRegistery.initialize_class(Settings, settings)
		for Class in Settings.__subclasses__():
			SettingsRegistery.initialize_class(Class, settings)

	@staticmethod
	def save():
		sublime.save_settings('debugger.sublime-settings')

