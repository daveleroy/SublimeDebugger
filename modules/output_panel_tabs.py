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

	def invalidated_layout(self):
		self.controls_and_tabs_phantom.update()
		self.controls_and_tabs_phantom.render()
