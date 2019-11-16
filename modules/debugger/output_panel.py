from ..typecheck import *

import sublime
import sublime_plugin

from .. import core
from .. import ui
from ..libs import asyncio

from ..debugger.util import get_setting

 	
if int(sublime.version()) < 4000:
	_phantom_text = " \u200b\u200b\u200b\u200b\u200b"
else:
	_phantom_text = "      "

class OutputPhantomsPanel:
	panels = {} #type: Dict[int, OutputPhantomsPanel]

	@staticmethod
	def for_window(window: sublime.Window) -> 'Optional[OutputPhantomsPanel]':
		return OutputPhantomsPanel.panels.get(window.id())

	def __init__(self, window: sublime.Window, name: str) -> None:
		self.header_text = ""
		self.name = name
		self.window = window

		self.view = window.create_output_panel(name)
		self.show()

		# we need enough space to place our phantoms in increasing regions (1, 1), (1, 2)... etc
		# otherwise they will get reordered when one of them gets redrawn
		# we use new lines so we don't have extra space on the rhs
		self.view.run_command('insert', {
			'characters': _phantom_text
		})
		settings = self.view.settings()
		settings.set("margin", 0)
		settings.set('line_padding_top', 0)
		settings.set('gutter', False)
		settings.set('word_wrap', False)
		settings.set('line_spacing', 0)
		settings.set('context_menu', 'Widget Debug.sublime-menu')

		self.view.sel().clear()
		self.hack_to_get_view_to_not_freak_out_when_you_click_on_the_edge()

		OutputPhantomsPanel.panels[self.window.id()] = self

	def isHidden(self) -> bool:
		return self.window.active_panel() != 'output.{}'.format(self.name)

	def hack_to_get_view_to_not_freak_out_when_you_click_on_the_edge(self):
		self.view.set_viewport_position((7, 0), animate=False)
		@core.coroutine
		def later():
			yield from asyncio.sleep(0)
			self.view.set_viewport_position((7, 0), animate=False)
		core.run(later())

	def show(self) -> None:
		self.window.run_command('show_panel', {
			'panel': 'output.{}'.format(self.name)
		})

	def hide(self) -> None:
		if self.window.active_panel() != self.name:
			return

		self.window.run_command('hide_panel', {
			'panel': 'output.{}'.format(self.name)
		})

	def phantom_location(self) -> int:
		return self.view.size() - len(_phantom_text) + 2

	def phantom_view(self) -> sublime.View:
		return self.view

	@property
	def ui_scale(self) -> float:
		return self.view.settings().get('font_size', 12)

	@ui_scale.setter
	def ui_scale(self, value: float) -> None:
		self.view.settings().set('font_size', value)

	def dispose(self) -> None:
		self.window.destroy_output_panel(self.name)
		del OutputPhantomsPanel.panels[self.window.id()]

class OutputPanelEventListener(sublime_plugin.EventListener):
	def on_post_window_command(self, window, command, args):
		if command == "show_panel":
			panel = OutputPhantomsPanel.for_window(window)
			if panel and get_setting(panel.view, "hide_status_bar", False):
				if args["panel"] == "output.Debugger":
					window.set_status_bar_visible(False)
				else:
					window.set_status_bar_visible(True)

		if command == "hide_panel":
			panel = OutputPhantomsPanel.for_window(window)
			if panel and get_setting(panel.view, "keep_panel_open", False):
				panel.show()