from __future__ import annotations
from typing import TYPE_CHECKING

from . import core
from . import ui
from .import dap

from .debugger_output_panel import DebuggerOutputPanel

from .views.tabbed import TabbedViewContainer
from .views.debugger import DebuggerTabbedView
from .views.callstack import CallStackTabbedView
from .views.variables import VariablesTabbedView
from .views.modules import ModulesTabbedView
from .views.sources import SourcesTabbedView

if TYPE_CHECKING:
	from .debugger import Debugger


class DebuggerMainOutputPanel(DebuggerOutputPanel, core.Dispose):
	def __init__(self, debugger: Debugger) -> None:
		super().__init__(debugger, 'Debugger', 'Callstack', show_tabs=False)

		self.on_input = core.Event[str]()
		self.on_navigate = core.Event[dap.SourceLocation]()
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

		self.debugger = debugger
		self.callstack = CallStackTabbedView(self.debugger, self)

		self.dispose_add([
			ui.Phantom(self.view, 0, name='Breakpoints')[
				TabbedViewContainer(width=30) [
					DebuggerTabbedView(self.debugger, debugger._on_navigate_to_source)
				]
			],
			ui.Phantom(self.view, 1, name='Callstack')[
				TabbedViewContainer(width_scale=0.65, width_additional=-30, width_additional_dip=-30)[
					self.callstack
				]
			],
			ui.Phantom(self.view, 2, name='Variables')[
				TabbedViewContainer(width_scale=0.35, width_additional=-30, width_additional_dip=-30) [
					VariablesTabbedView(self.debugger),
					ModulesTabbedView(self.debugger),
					SourcesTabbedView(self.debugger, debugger._on_navigate_to_source)
				]
			],
		])

	def updated_status(self):
		self.callstack.tabs.dirty()

	def scroll_to_end(self):
		self.view.set_viewport_position((0, 0), False)
