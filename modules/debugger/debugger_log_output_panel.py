from ..import core
import sublime_plugin
import sublime

from ..typecheck import *

def insert(view, message):
	core.edit(view, lambda edit: view.insert(edit, view.size(), f'{message}\n'))

def clear(view):
	core.edit(view, lambda edit: view.erase(edit, sublime.Region(0, view.size())))


class DebuggerLogOutputPanel(core.Logger):
	def __init__(self, window: sublime.Window):
		self.window = window
		self.panel = window.create_output_panel('Debugger Log')
		self.panel.assign_syntax('Packages/Debugger/Commands/LogPanel.sublime-syntax')
		settings = self.panel.settings()
		settings.set('word_wrap', False)

	def info(self, message: str):
		insert(self.panel, message)

	def error(self, message: str):
		insert(self.panel, f'error: {message}')

	def clear(self):
		clear(self.panel)

	def dispose(self):
		self.window.destroy_output_panel('Debugger Log')