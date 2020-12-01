from os import replace
from typing import ClassVar, Optional, Type

import sublime
from ..import core


class Settings:
	updated: core.Event[None] = core.Event()

	open_at_startup: bool = True
	ui_scale: int = 10
	font_face: str = 'Monospace'

	external_terminal: str = "terminus"
	hide_status_bar: bool = False
	keep_panel_open: bool = False
	bring_window_to_front_on_pause: bool = False

	log_info: bool = False
	log_exceptions: bool = True
	log_errors: bool = True

	node: Optional[str] = None

	# go.
	go_dlv: Optional[str] = None

	# lldb.
	lldb_show_disassembly: str = "auto"
	lldb_display_format: str = "auto"
	lldb_dereference_pointers: bool = True
	lldb_library: Optional[str] = None
	lldb_python: Optional[str] = None

	@classmethod
	def initialize(cls):
		dot_prefix_conversions = {
			'lldb_': 'lldb.',
			'go_': 'go.',
		}
		settings = sublime.load_settings('debugger.sublime-settings')

		for variable_name in vars(cls):
			if variable_name.startswith('__'): continue
			if variable_name == 'updated': continue
			if variable_name == 'initialize': continue
			if variable_name == 'save': continue

			key = variable_name
			for start, replace in dot_prefix_conversions.items():
				if key.startswith(start):
					key = key.replace(start, replace, 1)

			class Set:
				def __init__(self, key):
					self.key = key

				def __get__(self, obj, objtype):
					return settings.get(self.key)

				def __set__(self, obj, val):
					settings.set(self.key, val)
					sublime.save_settings('debugger.sublime-settings')

			s = Set(key)
			setattr(cls, variable_name, s)

		print(Settings.lldb_show_disassembly)

	@classmethod
	def save(self):
		sublime.save_settings('debugger.sublime-settings')


Settings = Settings() #type: ignore
