from __future__ import annotations
from typing import Any

import sublime

from .import core
from .import dap

class ProtocolWindow:
	def __init__(self) -> None:
		window = None

		for w in sublime.windows():
			if w.settings().has('debugger.window.protocol'):
				window = w

		self.window = window
		self.views: dict[dap.Session|None, sublime.View] = {}
		self.logs = []

	def open(self):
		if self.window and self.window.is_valid():
			self.window.bring_to_front()
		else:
			sublime.run_command('new_window')
			self.window = sublime.active_window()
			settings = self.window.settings()
			settings.set('debugger', True)
			settings.set('debugger.window', True)
			settings.set('debugger.window.protocol', True)

		self.window.run_command('show_panel', {'panel': 'console'})

	def clear(self):
		for view in self.views.values():
			view.close()

		self.views.clear()
		self.logs.clear()

	def dispose(self):
		self.clear()
		self.window = None

	def view_for_session(self, session: dap.Session|None):
		if view := self.views.get(session):
			return view

		assert self.window
		view = self.window.new_file(flags=sublime.ADD_TO_SELECTION)
		view.assign_syntax(core.package_path_relative('contributes/Syntax/DebuggerProtocol.sublime-syntax'))
		view.set_scratch(True)

		settings = view.settings()
		settings.set('word_wrap', False)
		settings.set('scroll_past_end', False)

		self.views[session] = view
		view.set_name(session and session.name or 'General')
		return view

	def platform_info(self):
		settings = sublime.load_settings("Preferences.sublime-settings")
		output =  ''
		output += f'-- platform: {sublime.platform()}-{sublime.arch()}\n'
		output += f'-- theme: {settings.get("theme")}\n'
		output += f'-- color_scheme: {settings.get("color_scheme")}\n'
		output += f'-- font_face: {settings.get("font_face")}\n'
		output += f'-- font_size: {settings.get("font_size")}\n'

		output += '\n'
		return output

	def log(self, type: str, value: Any, session: dap.Session|None = None):
		if not self.window:
			return

		self.logs.append(value)

		self.view_for_session(session).run_command('append', {
			'characters': f'{value}\n',
			'force': True,
			'scroll_to_end': True,
		})
