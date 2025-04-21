from __future__ import annotations
from typing import TYPE_CHECKING

from .. import ui
from . import css

from .debugger import DebuggerActionsView

if TYPE_CHECKING:
	from .debugger import Debugger
	from ..output_panel import OutputPanel


class OutputPanelTabsView(ui.span):
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
			with ui.span(css=css.tab_selected if is_selected else css.tab, on_click=lambda panel=panel, tab=panel.name: panel.open()):
				ui.spacer(1)
				ui.text(panel.name, css=css.label if is_selected else css.secondary)
				ui.spacer(1)
				if panel.status:
					ui.icon(panel.status, on_click=lambda panel=panel: panel.open_status())

			ui.spacer_dip(10)


class OutputPanelTabsBarView(ui.div):
	def __init__(self, debugger: Debugger, panel: OutputPanel):
		super().__init__(css=css.console_tabs_top if panel.show_tabs_top else css.console_tabs_bottom)

		self.actions = DebuggerActionsView(debugger)
		self.tabs = OutputPanelTabsView(debugger, panel)
		self.top = panel.show_tabs_top

	def render(self):
		with ui.div(width=self.layout.width):
			with ui.div(height=css.header_height):
				self.actions.append_stack()
				ui.spacer_dip(9)
				self.tabs.append_stack()

			if self.top:
				ui.div(height=0.25, css=css.seperator)
