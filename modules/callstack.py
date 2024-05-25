from __future__ import annotations
from typing import TYPE_CHECKING

from . import core
from . import ui
from .import dap

from .output_panel import OutputPanel

from .views.tabbed import TabbedViewContainer
from .views.debugger import DebuggerTabbedView
from .views.callstack import CallStackTabbedView
from .views.variables import VariablesTabbedView
from .views.modules import ModulesTabbedView
from .views.sources import SourcesTabbedView

if TYPE_CHECKING:
	from .debugger import Debugger


class CallstackOutputPanel(OutputPanel, core.Dispose):
	def __init__(self, debugger: Debugger) -> None:
		super().__init__(debugger, 'Debugger', 'Callstack', show_tabs=False, lock_selection=True)

		self.on_input = core.Event[str]()
		self.on_navigate = core.Event[dap.SourceLocation]()
		self.disposeables = []

		# we need enough space to place our phantoms in increasing regions (1, 1), (1, 2)... etc
		# otherwise they will get reordered when one of them gets redrawn
		# we use zero width characters so we don't have extra around phantoms
		self.view.run_command('insert', {
			'characters': '\u200c\u200c\u200c\u200c\u200c\u200c'
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
		# the -30 dip is to account for the space between phantoms
		width_additional_dip = -30

		# this is to account for the size of the breakpoints
		width_additional = -30

		with ui.Phantom(self.view, 0, name='Breakpoints') as phantom:
			self.dispose_add(phantom)

			with TabbedViewContainer(width=30) as tab:
				DebuggerTabbedView(self.debugger, debugger._on_navigate_to_source)

		with ui.Phantom(self.view, 3, name='Callstack') as phantom:
			self.dispose_add(phantom)

			with TabbedViewContainer(width_scale=0.5, width_additional=width_additional, width_additional_dip=width_additional_dip):
				self.callstack.append_stack()

		with ui.Phantom(self.view, 5, name='Variables') as phantom:
			self.dispose_add(phantom)

			with TabbedViewContainer(width_scale=0.5, width_additional=width_additional, width_additional_dip=width_additional_dip) as tab:
				VariablesTabbedView(self.debugger)
				ModulesTabbedView(self.debugger)
				SourcesTabbedView(self.debugger, debugger._on_navigate_to_source)


	def updated_status(self):
		self.callstack.tabs.dirty()

	def scroll_to_end(self):
		self.view.set_viewport_position((0, 0), False)
