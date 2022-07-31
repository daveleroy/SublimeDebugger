from __future__ import annotations
from os import kill
from typing import TYPE_CHECKING, Callable, Any, ClassVar, Dict

import sublime
import sublime_plugin
import sys

from .import core
from .import ui


from .views.debugger_panel import DebuggerActionsTab
from .views import css

if TYPE_CHECKING:
	from .debugger import Debugger

class DebuggerPanelTabs(ui.span):
	def __init__(self, debugger: Debugger, output_name: str):
		super().__init__()
		self.debugger = debugger
		self.debugger.on_output_panels_updated.add(self.dirty)
		self.output_name = output_name

	def __repr__(self) -> str:
		return super().__repr__() + self.output_name + str(self.children)

	def render(self):
		items: list[ui.span] = []

		for panel in self.debugger.output_panels:
			if panel.output_panel_name == self.output_name:
				csss = css.tab_panel_selected
			else:
				csss = css.tab_panel

			items.append(ui.click(lambda panel=panel: panel.open())[ui.span(css=csss)[
				ui.text(panel.name.replace('Debugger', '') or 'Callstack', css=css.label_secondary),
			]])

		return items

class DebuggerConsoleTabs(ui.div):
	def __init__(self, debugger: Debugger, output_name: str):
		super().__init__()
		self.debugger_actions = DebuggerActionsTab(debugger)
		self.tabs = DebuggerPanelTabs(debugger, output_name)

	def render(self):
		return ui.div(height=css.header_height)[
			self.debugger_actions,
			ui.spacer(1),
			self.tabs
		]

class DebuggerOutputPanel(sublime_plugin.TextChangeListener):
	on_opened: Callable[[], Any] | None = None
	on_closed: Callable[[], Any] | None = None

	panels: ClassVar[Dict[int, DebuggerOutputPanel]] = {}


	def __init__(self, debugger: Debugger, name: str, show_panel: bool = True, show_tabs = False):
		super().__init__()
		self.name = name
		self.window = debugger.window
		self.output_panel_name = f'output.{self.name}'
		# if a panel with the same name already exists add a unique id
		self._locked_selection = 0
		output_panel_name = f'output.{name}'

		id = 1
		while True:
			if not output_panel_name in self.window.panels():
				self.name = name
				self.output_panel_name = output_panel_name
				break

			name = f'{self.name}({id})'; id += 1
			output_panel_name = f'output.{name}'
				

		previous_panel = self.window.active_panel()
		self.view = self.window.create_output_panel(self.name)
		self.view.set_name(self.name)
		self.controls_and_tabs_phantom = None

		DebuggerOutputPanel.panels[self.view.id()] = self
		self.on_post_show_panel = core.on_post_show_panel.add(self._on_show_panel)
		self.on_pre_hide_panel = core.on_pre_hide_panel.add(self._on_hide_panel)

		settings = self.view.settings()
		settings.set('debugger', True)
		settings.set('debugger.output_panel_name', self.output_panel_name)
		settings.set('debugger.output_panel_tabs', show_tabs)
		settings.set('draw_unicode_white_space', 'none')
		settings.set('scroll_past_end', False)
		settings.set('context_menu', 'DebuggerWidget.sublime-menu')

		self.open()

		if not show_panel and previous_panel:
			self.window.run_command('show_panel', {
				'panel': previous_panel
			})


		self.removed_newline = None
		self.inside_on_text_changed = False
		self.attach(self.view.buffer())

		if show_tabs:
			self.controls_and_tabs_phantom = ui.Phantom(self.view, sublime.Region(self.view.size(), self.view.size()), sublime.LAYOUT_BLOCK) [
				DebuggerConsoleTabs(debugger, settings.get('debugger.output_panel_name'))
			]

		# self.scroll_to_end()
		# settings = self.view.settings()
		# # this tricks the panel into having a larger height
		# previous_line_padding_top = settings.get('line_padding_top')
		# settings.set('line_padding_top', 250)
		# self.open()
		# settings.set('line_padding_top', previous_line_padding_top)

	def dispose(self):
		if self.is_attached():
			self.detach()

		self.window.destroy_output_panel(self.name)
		self.on_post_show_panel.dispose()
		self.on_pre_hide_panel.dispose()
		if self.controls_and_tabs_phantom:
			self.controls_and_tabs_phantom.dispose()
		del DebuggerOutputPanel.panels[self.view.id()]

	def open(self):
		self.window.run_command('show_panel', {
			'panel': self.output_panel_name
		})

	def is_open(self) -> bool:
		return self.window.active_panel() == self.output_panel_name

	def _on_show_panel(self, window: sublime.Window):
		if window == self.window and window.active_panel() == self.output_panel_name:
			self.scroll_to_end()
			if self.on_opened: self.on_opened()

	def _on_hide_panel(self, window: sublime.Window, name: str):
		if self.on_closed and window == self.window and name == self.output_panel_name:
			# run on_closed after hiding the panel otherwise showing other panels will not work
			sublime.set_timeout(self.on_closed, 0)

	def is_locked_selection(self): 
		return self._locked_selection != 0

	def scroll_to_end(self):
		self.lock_selection_temporarily()
		sublime.set_timeout(lambda:self.view.set_viewport_position((0, sys.maxsize), False), 0)

	def lock_selection(self):
		self._locked_selection += 1

	def unlock_selection(self):
		self._locked_selection -= 1

	def lock_selection_temporarily(self):
		self.lock_selection()
		sublime.set_timeout(self.unlock_selection, 100)


	def ensure_new_line(self, text: str, at: int|None = None):
		if at is None:
			at = self.view.size()

		if self.removed_newline == at:
			return text

		if at != 0 and self.view.substr(at -1) != '\n':
			text = '\n' + text

		return text		


	def on_text_changed(self, changes):
		if self.inside_on_text_changed:
			return

		self.inside_on_text_changed  = True

		# re-insert the newline we removed
		if self.removed_newline:
			removed_newline = self.view.transform_region_from(sublime.Region(self.removed_newline), self.removed_newline_change_id)
			self.removed_newline = None
			def insert(edit: sublime.Edit):
				self.view.insert(edit, removed_newline.a, '\n')

			core.edit(self.view, insert)

		

		at = self.view.size()-1
		last = self.view.substr(at)

		if self.view.size() > 25 and last == '\n':
			def insert(edit: sublime.Edit):
				self.view.erase(edit, sublime.Region(at, at+1))

			core.edit(self.view, insert)
			self.removed_newline = self.view.size()
			self.removed_newline_change_id = self.view.change_id()

		self.inside_on_text_changed  = False


		if self.controls_and_tabs_phantom:
			self.controls_and_tabs_phantom.dirty()


class DebuggerConsoleListener (sublime_plugin.EventListener):
	def __init__(self) -> None:
		super().__init__()
		self.phantoms = {}

	def on_selection_modified(self, view: sublime.View) -> None:
		panel = DebuggerOutputPanel.panels.get(view.id())
		if not panel: return

		# the view is locked so we do not allow changing the selection. 
		# This allows the view to be scrolled to the bottom without issues when the selection is changed.
		if panel.is_locked_selection():
			view.sel().clear()
