from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from .. import core
from .. import ui
from .. import dap
from .. import menus
from . import css

from .breakpoints import BreakpointsView
from .tabbed import TabbedView

if TYPE_CHECKING:
	from ..debugger import Debugger


class DebuggerTabbedView(TabbedView, core.Dispose):
	def __init__(self, debugger: Debugger, on_navigate_to_source: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__('Debugger')

		self.debugger = debugger

		self.breakpoints = BreakpointsView(debugger.breakpoints, on_navigate_to_source)

		self.last_adapter_configuration: dap.AdapterConfiguration | None = None
		self.actions_tab = DebuggerActionsTab(debugger)

		# self.process = ProcessView(debugger)

	def added(self) -> None:
		self.dispose_add(
			self.debugger.on_session_updated.add(lambda session: self.dirty()),
			self.debugger.on_session_active.add(self.on_selected_session),
			self.debugger.on_session_added.add(self.on_selected_session),
			self.debugger.project.on_updated.add(self.dirty),
		)

	def removed(self) -> None:
		self.dispose()

	def header(self, is_selected):
		self.actions_tab.append_stack()

	def on_selected_session(self, session: dap.Session):
		self.last_adapter_configuration = session.adapter_configuration
		self.dirty()

	def render(self):
		# looks like
		# current status
		# breakpoints ...

		if session := self.debugger.session:
			self.last_adapter_configuration = session.adapter_configuration

			if status := session.state.status:
				with ui.div(height=css.row_height):
					ui.text(status, css=css.secondary)

		if self.last_adapter_configuration:
			self.last_adapter_configuration.ui(self.debugger)

		self.breakpoints.append_stack()


class DebuggerActionsTab(ui.span, core.Dispose):
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

		ui.icon(ui.Images.shared.settings, on_click=lambda: menus.on_settings(self.debugger), title='Settings')
		ui.spacer(1)
		ui.icon(ui.Images.shared.play, on_click=self.debugger.start, title=f'Start: {name}' if name else 'Add/Select Configuration')
		ui.spacer(1)

		if self.debugger.is_stoppable():
			ui.icon(ui.Images.shared.stop, on_click=self.debugger.stop, title='Stop')
		else:
			ui.icon(ui.Images.shared.stop_disable, on_click=self.debugger.stop, title='Stop (Disabled)')

		if len(name) > 11:
			name = name[:10] + '…'
		else:
			name = name.ljust(11, ' ')

		ui.spacer(1)

		if not self.debugger.session:
			with ui.span(css=css.button_drop, on_click=lambda: menus.on_settings(self.debugger)):
				ui.text(name, css=css.secondary)
				ui.icon(ui.Images.shared.open, align_left=False)

		else:
			if self.debugger.is_running():
				ui.icon(ui.Images.shared.pause, on_click=self.debugger.pause, title='Pause')
			elif self.debugger.is_paused():
				ui.icon(ui.Images.shared.resume, on_click=self.debugger.resume, title='Continue')
			else:
				ui.icon(ui.Images.shared.pause_disable, on_click=self.debugger.pause, title='Pause (Disabled)')

			ui.spacer(1)

			if self.debugger.is_paused():
				ui.icon(ui.Images.shared.down, on_click=self.debugger.step_over, title='Step Over')
				ui.spacer(1)
				ui.icon(ui.Images.shared.left, on_click=self.debugger.step_out, title='Step Out')
				ui.spacer(1)
				ui.icon(ui.Images.shared.right, on_click=self.debugger.step_in, title='Step In')
			else:
				ui.icon(ui.Images.shared.down_disable, on_click=self.debugger.step_over, title='Step Over (Disabled)')
				ui.spacer(1)
				ui.icon(ui.Images.shared.left_disable, on_click=self.debugger.step_out, title='Step Out (Disabled)')
				ui.spacer(1)
				ui.icon(ui.Images.shared.right_disable, on_click=self.debugger.step_in, title='Step In (Disabled)')

			ui.spacer(1)
