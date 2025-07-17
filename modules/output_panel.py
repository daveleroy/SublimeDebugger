from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Any, ClassVar, cast

import sublime
import sublime_plugin


from . import core
from . import ui

from .settings import Settings

if TYPE_CHECKING:
	from .debugger import Debugger


SUPPORTS_IO_PANEL = sublime.version() >= '4198'

class OutputPanel(core.Dispose):
	on_opened: Callable[[], Any] | None = None
	on_opened_status: Callable[[], Any] | None = None

	from_view: ClassVar[dict[sublime.View, OutputPanel]] = {}
	from_input_view: ClassVar[dict[sublime.View, OutputPanel]] = {}
	from_output_panel_name: ClassVar[dict[str, OutputPanel]] = {}

	def __init__(
		self,
		debugger: Debugger,
		panel_name: str,
		name: str | None = None,
		show_panel=True,
		show_tabs=True,
		show_tabs_top=False,
		remove_last_newline=False,
		create=True,
		lock_selection=False,
		unlisted=False,
	):
		super().__init__()
		self.panel_name = self._get_free_output_panel_name(debugger.window, panel_name) if create else panel_name
		self.output_panel_name = f'output.{self.panel_name}'
		self.name = name or panel_name

		self.window = debugger.window
		self.create = create
		self.show_tabs = show_tabs
		self.show_tabs_top = show_tabs_top
		self.remove_last_newline = remove_last_newline
		self.debugger = debugger
		self.lock_selection = lock_selection

		self.status: ui.Image | None = None

		self.removed_newline: int | None = None

		previous_panel = self.window.active_panel()

		from .output_panel_tabs import OutputPanelTabsBottomPhantom, OutputPanelTabsPhantom

		if SUPPORTS_IO_PANEL:
			self.view, self.input_view = cast('tuple[sublime.View, sublime.View]', self.window.create_io_panel(self.panel_name, lambda i:  None))

			input_settings = self.input_view.settings()
			input_settings.set('line_padding_top', 0)
			input_settings.set('line_padding_bottom', 0)

			self.tabs_phantom = OutputPanelTabsPhantom(self, self.input_view)
		else:
			self.view = self.window.create_output_panel(self.panel_name, unlisted=unlisted)
			self.input_view = None

			if show_tabs_top:
				self.tabs_phantom = OutputPanelTabsPhantom(self, self.view)
			else:
				self.tabs_phantom = OutputPanelTabsBottomPhantom(self, self.view)

		settings = self.view.settings()
		settings.set('debugger', id(debugger))
		settings.set('debugger.output', True)
		settings.set('debugger.output.' + self.name.lower(), True)

		if create:
			settings.set('draw_unicode_white_space', 'none')
			settings.set('context_menu', 'DebuggerWidget.sublime-menu')
			settings.set('is_widget', True)
			settings.set('rulers', [])

		OutputPanel.from_view[self.view] = self
		OutputPanel.from_output_panel_name[self.output_panel_name] = self

		if self.input_view:
			OutputPanel.from_input_view[self.input_view] = self

		settings.set('scroll_past_end', False)
		settings.set('gutter', False)

		# this is just a hack to get the output panel to have a bigger height
		self.update_settings()
		font_size = cast(float, settings.get('font_size') or 12)
		scaled_font = font_size * (Settings.console_minimum_height + 1.75) / 5
		settings.set('font_size', scaled_font)  # this will be removed in update_settings()
		self.open()

		self.update_settings()

		if not show_panel and previous_panel:
			self.window.run_command('show_panel', {'panel': previous_panel})

		self.debugger.add_output_panel(self)
		self.dispose_add(
			self.tabs_phantom,
			lambda: self.debugger.remove_output_panel(self),
		)

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
		self.debugger.on_output_panels_updated()

	def dispose(self):
		super().dispose()

		if not OutputPanel.from_view.get(self.view):
			return

		# remove debugger markers we added
		else:
			settings = self.view.settings()
			del settings['debugger']
			del settings['debugger.output']
			del settings['debugger.output.' + self.name.lower()]

		del OutputPanel.from_view[self.view]
		del OutputPanel.from_output_panel_name[self.output_panel_name]

		if self.input_view:
			del OutputPanel.from_input_view[self.input_view]

		if self.create:
			self.window.destroy_output_panel(self.panel_name)

	def _get_free_output_panel_name(self, window: sublime.Window, name: str) -> str:
		id = 1
		result = name
		while True:
			if not f'output.{result}' in window.panels():
				return result

			result = f'{name} {id}'
			id += 1

	def open(self):
		if not self.view.is_valid():
			self.dispose()
			return

		self.window.bring_to_front()
		self.window.run_command('show_panel', {'panel': self.output_panel_name})
		self.window.focus_view(self.view)

	def open_status(self):
		if on_opened_status := self.on_opened_status:
			on_opened_status()
		else:
			self.open()

	def is_open(self) -> bool:
		return self.window.active_panel() == self.output_panel_name

	def on_show_panel(self):
		if self.on_opened:
			self.on_opened()

		self.force_invalidate_layout()

	def force_invalidate_layout(self):
		self.tabs_phantom.force_refresh()

	def scroll_to_end(self):
		sel = self.view.sel()
		core.edit(
			self.view,
			lambda edit: (
				sel.clear(),
				sel.add(self.view.size()),
			),
		)

		if self.show_tabs_top:
			self.view.set_viewport_position((0, 0), False)
		else:
			height = self.view.layout_extent()[1]
			self.view.set_viewport_position((0, height), False)

		if self.window.active_view() == self.input_view:
			self.window.focus_view(self.view)

		if input_view := self.input_view:
			sublime.set_timeout(lambda: input_view.set_viewport_position((0, 0), False))

	def at(self):
		return self.view.size()

	def on_selection_modified(self): ...
	def on_activated(self): ...
	def on_deactivated(self): ...
	def on_text_command(self, command_name: str, args: Any): ...
	def on_post_text_command(self, command_name: str, args: Any): ...
	def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool | None: ...
	def on_query_completions(self, prefix: str, locations: list[int]) -> Any: ...


class OutputPanelEventListener(sublime_plugin.EventListener):
	def on_selection_modified(self, view: sublime.View) -> None:
		panel = OutputPanel.from_view.get(view)
		if not panel:
			return

		# the view is locked so we do not allow changing the selection.
		# This allows the view to be scrolled to the bottom without issues when the selection is changed.
		if panel.lock_selection:
			view.sel().clear()

		panel.on_selection_modified()

	def on_activated(self, view: sublime.View):
		# block the input view from gaining focus (it changes color when it has focus which we do not like) and can shift positions down
		if panel := OutputPanel.from_input_view.get(view):
			panel.window.focus_view(panel.view)
			# changing viewport has to be done the next cycle or it does not change
			sublime.set_timeout(lambda: view.set_viewport_position((0, 0), False))
			return

		if panel := OutputPanel.from_view.get(view):
			panel.on_activated()

	def on_deactivated(self, view: sublime.View):
		if panel := OutputPanel.from_view.get(view):
			panel.on_deactivated()

	def on_text_command(self, view: sublime.View, command_name: str, args: Any):
		if panel := OutputPanel.from_view.get(view):
			return panel.on_text_command(command_name, args)

	def on_post_text_command(self, view: sublime.View, command_name: str, args: Any):
		if panel := OutputPanel.from_view.get(view):
			return panel.on_post_text_command(command_name, args)

	def on_query_context(self, view: sublime.View, key: str, operator: int, operand: Any, match_all: bool) -> bool | None:
		if not key.startswith('debugger.'):
			return None

		if panel := OutputPanel.from_view.get(view):
			return panel.on_query_context(key, operator, operand, match_all)

		return None

	def on_query_completions(self, view: sublime.View, prefix: str, locations: list[int]) -> Any:
		if panel := OutputPanel.from_view.get(view):
			return panel.on_query_completions(prefix, locations)
