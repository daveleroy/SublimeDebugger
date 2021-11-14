from __future__ import annotations
from typing import Callable, Any

import sublime
from .import core
from .settings import Settings


class OutputPanel:
	on_opened: Callable[[], Any] | None = None
	on_hidden: Callable[[], Any] | None = None

	def __init__(self, window: sublime.Window, name: str, show_panel: bool = True):
		self.name = name
		self.window = window
		self.output_panel_name = f'output.{self.name}'

		# if a panel with the same name already exists add a unique id
		if self.output_panel_name in self.window.panels():
			self.name += f'({id(self)})'
			self.output_panel_name = f'output.{self.name}'

		previous_panel = self.window.active_panel()
		self.view = self.window.create_output_panel(self.name)
		if not show_panel and previous_panel:
			self.window.run_command('show_panel', {
				'panel': previous_panel
			})

		self.on_post_show_panel = core.on_post_show_panel.add(self.on_show_panel)
		self.on_pre_hide_panel = core.on_pre_hide_panel.add(self.on_hide_panel)

		# settings = self.view.settings()
		# # this tricks the panel into having a larger height
		# previous_line_padding_top = settings.get('line_padding_top')
		# settings.set('line_padding_top', 75)
		# self.open()
		# settings.set('line_padding_top', previous_line_padding_top)

	def on_show_panel(self, window: sublime.Window):
		if self.on_opened and window == self.window and window.active_panel() == self.output_panel_name:
			self.on_opened()

	def on_hide_panel(self, window: sublime.Window):
		if self.on_hidden and window == self.window and window.active_panel() == self.output_panel_name:
			self.on_hidden()

	def dispose(self):
		print(f'OutputPanel: dispose {self.name}')
		self.window.destroy_output_panel(self.name)
		self.on_post_show_panel.dispose()
		self.on_pre_hide_panel.dispose()

	def open(self):
		self.window.run_command('show_panel', {
			'panel': self.output_panel_name
		})

	def clear(self):
		view = self.view
		core.edit(view, lambda edit: view.erase(edit, sublime.Region(0, view.size())))

	def write(self, text: str):
		self.view.run_command('append', {
			'characters': text,
			'force': True,
		})


class DebuggerProtocolLogger(core.Logger):
	def __init__(self, window: sublime.Window):
		self.window = window
		self.panel = OutputPanel(window, 'Protocol', show_panel=False)
		self.panel.view.assign_syntax('Packages/Debugger/Commands/LogPanel.sublime-syntax')
		settings = self.panel.view.settings()
		settings.set('word_wrap', False)

		self.on_post_show_panel = core.on_post_show_panel.add(self.show_panel)
		self.on_pre_hide_panel = core.on_pre_hide_panel.add(self.hide_panel)

		self.pending: list[str] = []
		self.is_hidden = True

	def show_panel(self, window: sublime.Window):
		name = window.active_panel()
		if name == self.panel.output_panel_name:
			self.is_hidden = False
			self.write_pending()
		else:
			self.is_hidden = True

	def hide_panel(self, window: sublime.Window):
		self.is_hidden = True

	def write_pending(self):
		for pending in self.pending:
			self.panel.write(pending + '\n')
		self.pending.clear()

	def write_pending_if_needed(self):
		if not self.is_hidden:
			self.write_pending()

	def info(self, value: str):
		self.pending.append(value)
		self.write_pending_if_needed()

	def error(self, value: str):
		self.pending.append(f'error: {value}')
		self.write_pending_if_needed()

	def show(self):
		self.panel.open()

	def clear(self):
		self.pending.clear()
		self.panel.clear()

	def dispose(self):
		self.panel.dispose()
		self.on_post_show_panel.dispose()
		self.on_pre_hide_panel.dispose()

_phantom_text = '\u200F\u200F\u200F\u200F\u200F'

class DebuggerOutputPanel(OutputPanel):
	def __init__(self, window: sublime.Window):
		super().__init__(window, 'Debugger', show_panel=True)
		self.window = window

		# we need enough space to place our phantoms in increasing regions (1, 1), (1, 2)... etc
		# otherwise they will get reordered when one of them gets redrawn
		# we use zero width characters so we don't have extra around phantoms
		self.view.run_command('insert', {
			'characters': _phantom_text
		})

		settings = self.view.settings()
		settings.set('margin', 0)
		settings.set('line_padding_top', 3)
		settings.set('gutter', False)
		settings.set('word_wrap', True)
		settings.set('wrap_width', 0)
		settings.set('line_spacing', 0)
		settings.set('context_menu', 'Widget Debug.sublime-menu')
		settings.set('draw_centered', True)
		settings.set('draw_unicode_white_space', 'none')
		settings.set('draw_unicode_bidi', False)
		settings.set('is_widget', True)
		settings.set('sublime_debugger', True)
		settings.set('font_face', Settings.font_face)
		self.view.sel().clear()
		self.view.set_read_only(True)
		
		def on_hide_panel(window: sublime.Window):
			name = window.active_panel() or ''

			# show main debugger panel after closing other debugger panels
			if window == self.window and name != 'output.Debugger' and name.startswith('output.Debugger:'):
				core.log_info(f'Showing debug panel')
				self.panel_show()
				return True

			if Settings.hide_status_bar:
				self.window.set_status_bar_visible(True)

			return False

		def on_show_panel(window: sublime.Window):
			name = window.active_panel()
			if Settings.hide_status_bar:
				if name != 'output.Debugger':
					self.window.set_status_bar_visible(True)
				else:
					self.window.set_status_bar_visible(False)

		core.on_pre_hide_panel.add(on_hide_panel)
		core.on_post_show_panel.add(on_show_panel)

	def is_panel_visible(self) -> bool:
		return self.window.active_panel() == 'output.Debugger'

	def set_ui_scale(self, ui_scale: float):
		self.view.settings().set('font_size', ui_scale)

	def panel_show(self) -> None:
		self.window.run_command('show_panel', {
			'panel': 'output.{}'.format('Debugger')
		})

	def panel_hide(self) -> None:
		if self.window.active_panel() != 'Debugger':
			return

		self.window.run_command('hide_panel', {
			'panel': 'output.{}'.format('Debugger')
		})

	def panel_phantom_location(self) -> int:
		return 0

	def panel_phantom_view(self) -> sublime.View:
		return self.view

