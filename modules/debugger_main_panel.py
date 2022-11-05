from __future__ import annotations
from typing import TYPE_CHECKING, Callable, Any

import sublime

from . import core
from . import ui
from .import dap

from .settings import Settings
from .views.modules import ModulesPanel
from .views.sources import SourcesPanel
from .views.callstack import CallStackPanel

from .views.debugger_panel import DebuggerPanel
from .views.variables_panel import VariablesPanel
from .views.tabbed_panel import TabbedPanel

from .debugger_output_panel import DebuggerOutputPanel

if TYPE_CHECKING:
	from .debugger import Debugger


class DebuggerMainOutputPanel(DebuggerOutputPanel):
	def __init__(self, debugger: Debugger) -> None:
		super().__init__(debugger, 'Debugger', 'Callstack', show_tabs=False)

		self.on_input: core.Event[str] = core.Event()
		self.on_navigate: core.Event[dap.SourceLocation] = core.Event()
		self.disposeables = []

		self.lock_selection()

		# we need enough space to place our phantoms in increasing regions (1, 1), (1, 2)... etc
		# otherwise they will get reordered when one of them gets redrawn
		# we use zero width characters so we don't have extra around phantoms
		self.view.run_command('insert', {
			'characters': '\u200c\u200c'
		})
		self.view.set_read_only(True)

		settings = self.view.settings()
		settings.set('margin', 0)
		settings.set('line_padding_top', 3)

		# for some reason if word_wrap is False there is a horizontal scrollbar when the UI fits the window perfectly
		# If set to True and the wrap_width set to bigger than the window then there is no scrollbar unlesss the UI is sized too large
		settings.set('word_wrap', True)
		settings.set('wrap_width', 100000)

		settings.set('context_menu', 'DebuggerWidget.sublime-menu')
		settings.set('is_widget', True)

		self.debugger = debugger

		self.debugger_panel = DebuggerPanel(self.debugger, debugger._on_navigate_to_source)
		self.callstack_panel = CallStackPanel(self.debugger, self)

		self.middle_panel = TabbedPanel([], 0, width_scale=0.65, width_additional=-30)
		self.middle_panel.update([
			# self.console_panel,
			self.callstack_panel,
		])

		# self.middle_panel.select(self.callstack_panel)

		# right panels
		self.right_panel = TabbedPanel([], 0, width_scale=0.35, width_additional=-30)

		self.variables_panel = VariablesPanel(self.debugger)
		self.modules_panel = ModulesPanel(self.debugger)
		self.sources_panel = SourcesPanel(self.debugger, debugger._on_navigate_to_source)

		self.right_panel.update([
			self.variables_panel,
			self.modules_panel,
			self.sources_panel,
		])

		self.left = ui.Phantom(self.view, sublime.Region(0, 0), sublime.LAYOUT_INLINE)[
			self.debugger_panel
		]
		self.middle = ui.Phantom(self.view, sublime.Region(0, 1), sublime.LAYOUT_INLINE)[
			self.middle_panel
		]
		self.right = ui.Phantom(self.view, sublime.Region(0, 2), sublime.LAYOUT_INLINE)[
			self.right_panel
		]
		self.disposeables.extend([self.left, self.middle, self.right])

	def dispose(self):
		super().dispose()

		for d in self.disposeables:
			d.dispose()
		self.disposeables.clear()

	def updated_status(self):
		self.middle_panel.dirty()
		
	def scroll_to_end(self):
		self.view.set_viewport_position((0, 0), False)


