from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Any, ClassVar, Dict

import sublime
import sublime_plugin

from .import core
from .import ui

from .views.debugger import DebuggerActionsTab
from .views import css
from .settings import Settings

if TYPE_CHECKING:
	from .debugger import Debugger

class OutputPanelTabs(ui.span):
	def __init__(self, debugger: Debugger, panel: OutputPanel):
		super().__init__()
		self.debugger = debugger
		self.debugger.on_output_panels_updated.add(self.dirty)
		self.output_name = panel.output_panel_name
		self.show_tabs_top = panel.show_tabs_top

	def __repr__(self) -> str:
		return super().__repr__() + self.output_name + str(self.children)

	def render(self):
		for panel in self.debugger.output_panels:
			is_selected = panel.output_panel_name == self.output_name

			for tab in panel.tabs:
				tab_selected = is_selected and tab == panel.tab
				with ui.span(css=css.tab_selected if tab_selected else css.tab, on_click=lambda panel=panel, tab=tab: panel.open(tab)):
					ui.spacer(1)
					ui.text(tab, css=css.label if tab_selected else css.secondary)
					ui.spacer(1)
					if panel.status:
						ui.icon(panel.status, on_click=lambda panel=panel: panel.open_status())

				ui.spacer_dip(10)




class OutputPanelBar(ui.div):
	def __init__(self, debugger: Debugger, panel: OutputPanel):
		super().__init__(css=css.console_tabs_top if panel.show_tabs_top else css.console_tabs_bottom)

		self.actions = DebuggerActionsTab(debugger)
		self.tabs = OutputPanelTabs(debugger, panel)
		self.top = panel.show_tabs_top

	def render(self):
		with ui.div(width=self.layout.width - 5):
			with ui.div(height=css.header_height):
				self.actions.append_stack()
				ui.spacer_dip(9)
				self.tabs.append_stack()

			if self.top:
				ui.div(height=0.25, css=css.seperator)

class OutputPanel(core.Dispose):
	on_opened: Callable[[], Any] | None = None
	on_opened_status: Callable[[], Any] | None = None

	_panels: ClassVar[Dict[int, OutputPanel]] = {}
	_panels_by_output_panel_name: ClassVar[Dict[str, OutputPanel]] = {}

	@staticmethod
	def for_output_panel_name(output_panel_name: str) -> OutputPanel|None:
		return OutputPanel._panels_by_output_panel_name.get(output_panel_name)

	@staticmethod
	def for_view(view: sublime.View) -> OutputPanel|None:
		return OutputPanel._panels.get(view.id())


	def __init__(self,
			debugger: Debugger,
			panel_name: str,
			name: str|None = None,
			show_panel = True,
			show_tabs = True,
			show_tabs_top = False,
			remove_last_newline = False,
			create = True,
			lock_selection = False,
		):

		super().__init__()
		self.panel_name = self._get_free_output_panel_name(debugger.window, panel_name) if create else panel_name
		self.output_panel_name = f'output.{self.panel_name}'
		self.name = name or panel_name

		self.tab = self.name
		self.tabs = [self.name]

		self.window = debugger.window
		self.create = create
		self.show_tabs = show_tabs
		self.show_tabs_top = show_tabs_top
		self.remove_last_newline = remove_last_newline
		self.debugger = debugger
		self.lock_selection = lock_selection

		self.status: ui.Image|None = None

		self.removed_newline: int|None = None

		previous_panel = self.window.active_panel()
		self.view = self.window.find_output_panel(self.panel_name) or self.window.create_output_panel(self.panel_name)
		self.view.set_name(self.name)
		self.controls_and_tabs_phantom = None
		self.text_change_listener = None

		OutputPanel._panels[self.view.id()] = self
		OutputPanel._panels_by_output_panel_name[self.output_panel_name] = self

		settings = self.view.settings()
		settings.set('debugger', True)
		settings.set('debugger.output', True)
		settings.set('debugger.output.' + self.name.lower(), True)

		settings.set('scroll_past_end', False)
		settings.set('gutter', False)

		if create:
			settings.set('draw_unicode_white_space', 'none')
			settings.set('context_menu', 'DebuggerWidget.sublime-menu')
			settings.set('is_widget', True)
			settings.set('rulers', [])

		# this is just a hack to get the output panel to have a bigger height
		self.update_settings()
		scaled_font = settings.get('font_size', 12) * (Settings.minimum_console_height + 1.75) / 5
		settings.set('font_size', scaled_font) # this will be removed in update_settings()
		self.open()

		self.update_settings()

		if show_tabs and show_tabs_top:
			# 3 seems to be an inline for the content before and the content after is left aligned below the phantom which lets us put a phantom at the top of the ui if you use Region(0)
			self.controls_and_tabs_phantom = ui.Phantom(self.view, sublime.Region(0), 3)
			with self.controls_and_tabs_phantom:
				self.controls_and_tabs = OutputPanelBar(debugger, self)

			self.dispose_add([
				self.controls_and_tabs_phantom,
			])

		elif show_tabs:

			self.controls_and_tabs_phantom = ui.Phantom(self.view, sublime.Region(-1), sublime.LAYOUT_BLOCK)
			with self.controls_and_tabs_phantom:
				self.controls_and_tabs = OutputPanelBar(debugger, self)

			self.text_change_listener = OutputPanelBottomTextChangeListener(self)
			self.controls_and_tabs_phantom.on_layout_invalidated = self.text_change_listener.invalidated

			self.dispose_add([
				self.text_change_listener,
				self.controls_and_tabs_phantom,
			])

		else:
			self.text_change_listener = None
			self.controls_and_tabs = None
			self.controls_and_tabs_phantom = None

		debugger.add_output_panel(self)

		if self.text_change_listener:
			self.text_change_listener.on_text_changed([])

		if not show_panel and previous_panel:
			self.window.run_command('show_panel', {
				'panel': previous_panel
			})

	def update_settings(self):
		# these settings control the size of the ui calculated in ui/layout
		settings = self.view.settings()
		settings['internal_font_scale'] = Settings.internal_font_scale
		settings['internal_width_modifier'] = Settings.internal_width_modifier

		if Settings.font_size:
			settings['font_size'] = Settings.font_size
		else:
			settings.erase('font_size')

	def set_status(self, status: ui.Image):
		if self.status == status:
			return

		self.status = status

		# if the status of a panel changes we need to re-render all the output panels
		for panel in self.debugger.output_panels:
			panel.updated_status()

	def updated_status(self):
		if controls_and_tabs := self.controls_and_tabs:
			controls_and_tabs.dirty()

	def dispose(self):
		super().dispose()

		self.debugger.remove_output_panel(self)

		if self.create:
			self.window.destroy_output_panel(self.panel_name)

		# remove debugger markers we added
		else:
			settings = self.view.settings()
			del settings['debugger']
			del settings['debugger.output']
			del settings['debugger.output.' + self.name.lower()]

		del OutputPanel._panels[self.view.id()]

	def _get_free_output_panel_name(self, window: sublime.Window, name: str) -> str:
		id = 1
		while True:
			if not f'output.{name}' in window.panels():
				return name

			name = f'{name}({id})'
			id += 1

	def open(self, tab: str|None = None):
		self.tab = tab or self.tab
		self.window.bring_to_front()
		self.window.run_command('show_panel', {
			'panel': self.output_panel_name
		})
		# sublime.set_timeout(self.scroll_to_end, 5)

	def open_status(self):
		if on_opened_status := self.on_opened_status:
			on_opened_status()
		else:
			self.open()

	def is_open(self) -> bool:
		return self.window.active_panel() == self.output_panel_name

	def on_show_panel(self):
		# self.scroll_to_end()
		if self.on_opened:
			self.on_opened()

		if self.text_change_listener:
			self.text_change_listener.on_text_changed([])

	def scroll_to_end(self):
		sel = self.view.sel()
		core.edit(self.view, lambda edit: (
			sel.clear(),
			sel.add(self.view.size()),
		))

		if self.show_tabs_top:
			self.view.set_viewport_position((0, 0), False)
		else:
			height = self.view.layout_extent()[1]
			self.view.set_viewport_position((0, height), False)

		self.window.focus_view(self.view)

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

	def on_selection_modified(self): ...
	def on_activated(self): ...
	def on_deactivated(self): ...
	def on_text_command(self, command_name: str, args: Any): ...
	def on_post_text_command(self, command_name: str, args: Any): ...
	def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool|None: ...
	def on_query_completions(self, prefix: str, locations: list[int]) -> Any: ...


class DebuggerConsoleListener (sublime_plugin.EventListener):
	def on_selection_modified(self, view: sublime.View) -> None:
		panel = OutputPanel.for_view(view)
		if not panel: return

		# the view is locked so we do not allow changing the selection.
		# This allows the view to be scrolled to the bottom without issues when the selection is changed.
		if panel.lock_selection:
			view.sel().clear()

		panel.on_selection_modified()

	def on_activated(self, view: sublime.View):
		if panel := OutputPanel.for_view(view):
			panel.on_activated()

	def on_deactivated(self, view: sublime.View):
		if panel := OutputPanel.for_view(view):
			panel.on_deactivated()

	def on_text_command(self, view: sublime.View, command_name: str, args: Any):
		if panel := OutputPanel.for_view(view):
			return panel.on_text_command(command_name, args)

	def on_post_text_command(self, view: sublime.View, command_name: str, args: Any):
		if panel := OutputPanel.for_view(view):
			return panel.on_post_text_command(command_name, args)

	def on_query_context(self, view: sublime.View, key: str, operator: int, operand: Any, match_all: bool) -> bool|None:
		if not key.startswith('debugger.'):
			return None

		if panel := OutputPanel.for_view(view):
			return panel.on_query_context(key, operator, operand, match_all)

		return None

	def on_query_completions(self, view: sublime.View, prefix: str, locations: list[int]) -> Any:
		if panel := OutputPanel.for_view(view):
			return panel.on_query_completions(prefix, locations)

class OutputPanelBottomTextChangeListener(sublime_plugin.TextChangeListener):
	def __init__(self, panel: OutputPanel) -> None:
		super().__init__()
		self.panel = panel
		self.view = panel.view
		self.inside_on_text_changed = False
		self.attach(self.view.buffer())

	def invalidated(self, scroll=False):
		controls_and_tabs_phantom = self.panel.controls_and_tabs_phantom
		if not controls_and_tabs_phantom:
			return

		size = self.view.size()

		# if the size is 0 the phantom does not exist yet. We want render it before we make any calculations
		# otherwise we will be off by the height of the phantom
		if not size:
			controls_and_tabs_phantom.dirty()
			controls_and_tabs_phantom.render()


		height = self.view.layout_extent()[1]
		desired_height = self.view.viewport_extent()[1]


		controls_and_tabs_phantom.vertical_offset = max((desired_height-height) + controls_and_tabs_phantom.vertical_offset, 0)
		controls_and_tabs_phantom.render_if_out_of_position()

	def dispose(self):
		if self.is_attached():
			self.detach()

	def on_text_changed(self, changes: list[sublime.TextChange]):

		if self.inside_on_text_changed:
			return

		self.inside_on_text_changed  = True
		core.edit(self.view, self._on_text_changed)
		self.inside_on_text_changed  = False


	def _on_text_changed(self, edit: sublime.Edit):
		is_readonly = self.view.is_read_only()
		self.view.set_read_only(False)

		# re-insert the newline we removed
		if self.panel.removed_newline:
			removed_newline = self.view.transform_region_from(sublime.Region(self.panel.removed_newline), self.removed_newline_change_id)
			self.panel.removed_newline = None
			self.view.insert(edit, removed_newline.a, '\n')

		at = self.panel.at() - 1
		last = self.view.substr(at)

		# remove newline
		if self.panel.remove_last_newline and last == '\n':
			self.view.erase(edit, sublime.Region(at, at+1))
			self.panel.removed_newline = at
			self.removed_newline_change_id = self.view.change_id()

		self.view.set_read_only(is_readonly)

		self.invalidated()

		# Figure out a better way that doesn't always scroll to the bottom when new content comes in
		sublime.set_timeout(lambda: self.view.set_viewport_position((0, self.view.layout_extent()[1]), False), 0)
