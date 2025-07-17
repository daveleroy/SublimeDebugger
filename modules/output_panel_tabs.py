from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Protocol

import sublime
import sublime_plugin

from . import core
from . import ui


if TYPE_CHECKING:
	from .output_panel import OutputPanel
	from .views.output_panel_tabs import OutputPanelTabsView


class OutputPanelTabsPhantom(core.Dispose):
	def __init__(self, panel: OutputPanel, view: sublime.View):
		self.panel = panel
		self.view = view

		self.controls_and_tabs_phantom = ui.Phantom(view, sublime.Region(0), 3)
		with self.controls_and_tabs_phantom:
			from .views.output_panel_tabs import OutputPanelTabsView
			self.controls_and_tabs = OutputPanelTabsView(panel)

		self.dispose_add(
			self.controls_and_tabs_phantom,
		)

		# TODO: fix this? This shouldn't be rquired
		# fixes flixer when first creating panel like the size is not correct or something
		sublime.set_timeout(lambda: ui.update_and_render(True))

	def force_refresh(self): ...


class OutputPanelTabsBottomPhantom(core.Dispose):
	def __init__(self, panel: OutputPanel, view: sublime.View):
		self.view = view
		self.panel = panel

		self.controls_and_tabs_phantom = ui.Phantom(view, sublime.Region(-1), sublime.LAYOUT_BLOCK)
		with self.controls_and_tabs_phantom:
			self.controls_and_tabs = OutputPanelTabsView(panel)

		self.text_change_listener = OutputPanelBottomTextChangeListener(self)
		self.controls_and_tabs_phantom.on_layout_invalidated = self.text_change_listener.invalidated

		self.dispose_add(
			[
				self.text_change_listener,
				self.controls_and_tabs_phantom,
			]
		)

		# TODO: fix this? This shouldn't be rquired
		# fixes flixer when first creating panel like the size is not correct or something
		sublime.set_timeout(lambda: ui.update_and_render(True))

	def force_refresh(self):
		self.text_change_listener.on_text_changed([])


class OutputPanelBottomTextChangeListener(sublime_plugin.TextChangeListener):
	def __init__(self, phantom: OutputPanelTabsBottomPhantom) -> None:
		super().__init__()
		self.phantom = phantom
		self.panel = phantom.panel
		self.view = self.phantom.view
		self.removed_newline_change_id: Any = None

		self.inside_on_text_changed = False
		self.attach(self.view.buffer())

	def invalidated(self, scroll=False):
		controls_and_tabs_phantom = self.phantom.controls_and_tabs_phantom
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

		controls_and_tabs_phantom.vertical_offset = max((desired_height - height) + controls_and_tabs_phantom.vertical_offset, 0)
		controls_and_tabs_phantom.render_if_out_of_position()

	def dispose(self):
		if self.is_attached():
			self.detach()

	def on_text_changed(self, changes: list[sublime.TextChange]):
		if self.inside_on_text_changed:
			return

		self.inside_on_text_changed = True
		core.edit(self.view, self._on_text_changed)
		self.inside_on_text_changed = False

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
			self.view.erase(edit, sublime.Region(at, at + 1))
			self.panel.removed_newline = at
			self.removed_newline_change_id = self.view.change_id()

		self.view.set_read_only(is_readonly)
		self.invalidated()
