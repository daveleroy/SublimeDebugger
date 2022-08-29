from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Any, ClassVar, Dict

import sublime
import sublime_plugin

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

			name = panel.name.replace('Debugger', '') or 'Callstack'

			items.append(ui.click(lambda panel=panel: panel.open())[ui.span(css=csss)[
				ui.text(name, css=css.label_secondary),
				ui.spacer(1),
				ui.click(lambda panel=panel: panel.open_status()) [
					panel.status and ui.icon(panel.status)
				]
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
	on_opened_status: Callable[[], Any] | None = None

	on_closed: Callable[[], Any] | None = None
	
	panels: ClassVar[Dict[int, DebuggerOutputPanel]] = {}

	def __init__(self, debugger: Debugger, name: str, show_panel = True, show_tabs = True):
		super().__init__()
		self.name = self._get_free_output_panel_name(debugger.window, name)
		self.output_panel_name = f'output.{self.name}'

		self.window = debugger.window
		self.show_tabs = show_tabs
		self.debugger = debugger
		
		# if a panel with the same name already exists add a unique id
		self._locked_selection = 0
		self.status: ui.Image|None = None

		previous_panel = self.window.active_panel()
		self.view = self.window.create_output_panel(self.name)
		self.view.set_name(self.name)
		self.controls_and_tabs_phantom = None

		DebuggerOutputPanel.panels[self.view.id()] = self
		self.on_post_show_panel = core.on_post_show_panel.add(self._on_show_panel)
		self.on_pre_hide_panel = core.on_pre_hide_panel.add(self._on_hide_panel)

		settings = self.view.settings()
		settings.set('debugger', True)
		settings.set('debugger.output_panel', True)
		settings.set('debugger.output_panel_name', self.output_panel_name)
		settings.set('debugger.output_panel_tabs', show_tabs)
		settings.set('draw_unicode_white_space', 'none')
		settings.set('scroll_past_end', False)
		settings.set('context_menu', 'DebuggerWidget.sublime-menu')
		settings.set('gutter', False)
		self.open()

		if not show_panel and previous_panel:
			self.window.run_command('show_panel', {
				'panel': previous_panel
			})


		self.removed_newline = None
		self.inside_on_text_changed = False
		self.attach(self.view.buffer())


		if show_tabs:
			self.controls_and_tabs = DebuggerConsoleTabs(debugger, settings.get('debugger.output_panel_name'))
			self.controls_and_tabs_phantom = ui.Phantom(self.view, sublime.Region(self.view.size(), self.view.size()), sublime.LAYOUT_BLOCK) [
				self.controls_and_tabs
			]
		else:
			self.controls_and_tabs = None
			self.controls_and_tabs_phantom = None

		debugger.add_output_panel(self)
		# self.scroll_to_end()
		# settings = self.view.settings()
		# # this tricks the panel into having a larger height
		# previous_line_padding_top = settings.get('line_padding_top')
		# settings.set('line_padding_top', 250)
		# self.open()
		# settings.set('line_padding_top', previous_line_padding_top)

	def set_status(self, status: ui.Image):
		self.status = status
		
		# if the status of a panel changes we need to re-render all the output panels
		for panel in self.debugger.output_panels:
			panel.updated_status()

	def updated_status(self):
		if controls_and_tabs := self.controls_and_tabs:
			controls_and_tabs.dirty()		

	def dispose(self):
		self.debugger.remove_output_panel(self)

		if self.is_attached():
			self.detach()

		self.window.destroy_output_panel(self.name)
		self.on_post_show_panel.dispose()
		self.on_pre_hide_panel.dispose()
		if self.controls_and_tabs_phantom:
			self.controls_and_tabs_phantom.dispose()
		del DebuggerOutputPanel.panels[self.view.id()]

	def _get_free_output_panel_name(self, window: sublime.Window, name: str) -> str:
		id = 1
		while True:
			if not f'output.{name}' in window.panels():
				return name

			name = f'{name}({id})'
			id += 1

	def open(self):
		self.window.run_command('show_panel', {
			'panel': self.output_panel_name
		})

	def open_status(self):
		if on_opened_status := self.on_opened_status:
			on_opened_status()
		else:
			self.open()

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
		# self.lock_selection_temporarily()
		height = self.view.layout_extent()[1]
		self.view.set_viewport_position((0, height), False)

	def lock_selection(self):
		self._locked_selection += 1

	def unlock_selection(self):
		self._locked_selection -= 1

	def lock_selection_temporarily(self):
		self.lock_selection()
		sublime.set_timeout(self.unlock_selection, 100)

	def at(self):
		return self.view.size()

	def ensure_new_line(self, text: str, at: int|None = None):
		if at is None:
			at = self.at()

		if self.removed_newline == at:
			return text

		if at != 0 and self.view.substr(at -1) != '\n':
			text = '\n' + text

		return text		

	def on_text_changed_edit(self, edit: sublime.Edit):
		# ensure panel is at least 25 lines since we need the height of the content to be more than its viewport height
		if self.show_tabs:
			line_count = self.view.rowcol(self.view.size())[0] + 1

			if line_count < 25:
				self.view.insert(edit, 0, 25 * '\n')

		# re-insert the newline we removed
		if self.removed_newline:
			removed_newline = self.view.transform_region_from(sublime.Region(self.removed_newline), self.removed_newline_change_id)
			self.removed_newline = None
			self.view.insert(edit, removed_newline.a, '\n')

		at = self.at() - 1
		last = self.view.substr(at)

		# remove newline
		if last == '\n':
			self.view.erase(edit, sublime.Region(at, at+1))
			self.removed_newline = at
			self.removed_newline_change_id = self.view.change_id()

		if self.controls_and_tabs_phantom:
			self.controls_and_tabs_phantom.dirty()


	def on_text_changed(self, changes):
		if self.inside_on_text_changed:
			return

		self.inside_on_text_changed  = True
		core.edit(self.view, self.on_text_changed_edit)
		self.inside_on_text_changed  = False

	def on_selection_modified(self): ...
	def on_activated(self): ...
	def on_deactivated(self): ...
	def on_text_command(self, command_name: str, args: Any): ...
	def on_query_context(self, key: str, operator: str, operand: str, match_all: bool) -> bool: ...
	def on_query_completions(self, prefix: str, locations: list[int]) -> Any: ...


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

		panel.on_selection_modified()

	def on_activated(self, view: sublime.View):
		if panel := DebuggerOutputPanel.panels.get(view.id()):
			panel.on_activated()

	def on_deactivated(self, view: sublime.View):
		if panel := DebuggerOutputPanel.panels.get(view.id()):
			panel.on_deactivated()

	def on_text_command(self, view: sublime.View, command_name: str, args: Any):
		if panel := DebuggerOutputPanel.panels.get(view.id()):
			return panel.on_text_command(command_name, args)

	def on_query_context(self, view: sublime.View, key: str, operator: str, operand: str, match_all: bool) -> bool:
		if key != 'debugger':
			return False

		if panel := DebuggerOutputPanel.panels.get(view.id()):
			return panel.on_query_context(key, operator, operand, match_all)

		return False

	def on_query_completions(self, view: sublime.View, prefix: str, locations: list[int]) -> Any:
		if panel := DebuggerOutputPanel.panels.get(view.id()):
			return panel.on_query_completions(prefix, locations)