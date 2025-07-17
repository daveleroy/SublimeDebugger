from __future__ import annotations
from typing import TYPE_CHECKING


from .. import ui
from .. import core
from . import css

from ..commands.commands import (
	ChangeConfiguration,
	Continue,
	Pause,
	Start,
	StepIn,
	StepOut,
	StepOver,
	Stop,
)

if TYPE_CHECKING:
	from ..output_panel import OutputPanel
	from ..debugger import Debugger


class OutputPanelTabsView(ui.div, core.Dispose):
	def __init__(self, panel: OutputPanel):
		super().__init__(css=css.console_tabs)

		self.actions = ActionsView(panel.debugger)
		self.tabs = TabsView(panel)

	def render(self):
		with ui.div(width=self.layout.width):
			with ui.div(height=css.header_height):
				self.actions.append_stack()
				ui.spacer_dip(9)
				self.tabs.append_stack()


class TabsView(ui.span, core.Dispose):
	def __init__(self, panel: OutputPanel):
		super().__init__(css=css.console_tabs)
		self.panel = panel

	def added(self) -> None:
		self.dispose_add(
			self.panel.debugger.on_output_panels_updated.add(self.dirty),
		)

	def removed(self) -> None:
		self.dispose()

	def render(self):
		for panel in self.panel.debugger.output_panels:
			is_selected = panel == self.panel

			names = panel.name.split('\t', 2)

			with ui.span(css=css.tab_selected if is_selected else css.tab, on_click=lambda panel=panel, tab=panel.name: panel.open()):
				ui.spacer(1)
				if len(names) > 1:
					ui.text(names[1] + ':', css=css.bold if is_selected else css.secondary)
					ui.spacer(1)

				ui.text(names[0], css=css.bold if is_selected else css.secondary)
				ui.spacer(1)

				# if panel.status:
				# 	ui.icon(panel.status, on_click=lambda panel=panel: panel.open_status())

			ui.spacer_dip(10)


class ActionsView(ui.span, core.Dispose):
	def __init__(self, debugger: Debugger, css: ui.css | None = css.controls_panel) -> None:
		super().__init__(css=css)
		self.debugger = debugger

	def added(self) -> None:
		self.dispose_add(
			self.debugger.on_session_updated.add(lambda session: self.dirty()),
			self.debugger.on_session_removed.add(lambda _: self.dirty()),
			self.debugger.project.on_updated.add(lambda: self.dirty()),
		)

	def removed(self) -> None:
		self.dispose()

	def render(self):
		name = self.debugger.project.name

		ui.icon(ui.Images.shared.settings, on_click=lambda: self.debugger.run_action(ChangeConfiguration), title='Settings')
		ui.spacer(1)
		ui.icon(ui.Images.shared.play, on_click=lambda: self.debugger.run_action(Start), title=f'Start: {name}' if name else 'Add/Select Configuration')
		ui.spacer(1)

		if self.debugger.is_stoppable():
			ui.icon(ui.Images.shared.stop, on_click=lambda: self.debugger.run_action(Stop), title='Stop')
		else:
			ui.icon(ui.Images.shared.stop_disable, on_click=lambda: self.debugger.run_action(Stop), title='Stop (Disabled)')

		if len(name) > 11:
			name = name[:10] + '…'
		else:
			name = name.ljust(11, ' ')

		ui.spacer(1)

		if not self.debugger.session:
			with ui.span(css=css.button_drop, on_click=lambda: self.debugger.run_action(ChangeConfiguration)):
				ui.text(name, css=css.secondary)
				ui.icon(ui.Images.shared.open, align_left=False)

		else:
			if self.debugger.is_running():
				ui.icon(ui.Images.shared.pause, on_click=lambda: self.debugger.run_action(Pause), title='Pause')
			elif self.debugger.is_paused():
				ui.icon(ui.Images.shared.resume, on_click=lambda: self.debugger.run_action(Continue), title='Continue')
			else:
				ui.icon(ui.Images.shared.pause_disable, on_click=lambda: self.debugger.run_action(Pause), title='Pause (Disabled)')

			ui.spacer(1)

			if self.debugger.is_paused():
				ui.icon(ui.Images.shared.down, on_click=lambda: self.debugger.run_action(StepOver), title='Step Over')
				ui.spacer(1)
				ui.icon(ui.Images.shared.left, on_click=lambda: self.debugger.run_action(StepOut), title='Step Out')
				ui.spacer(1)
				ui.icon(ui.Images.shared.right, on_click=lambda: self.debugger.run_action(StepIn), title='Step In')
			else:
				ui.icon(ui.Images.shared.down_disable, on_click=lambda: self.debugger.run_action(StepOver), title='Step Over (Disabled)')
				ui.spacer(1)
				ui.icon(ui.Images.shared.left_disable, on_click=lambda: self.debugger.run_action(StepOut), title='Step Out (Disabled)')
				ui.spacer(1)
				ui.icon(ui.Images.shared.right_disable, on_click=lambda: self.debugger.run_action(StepIn), title='Step In (Disabled)')

			ui.spacer(1)
