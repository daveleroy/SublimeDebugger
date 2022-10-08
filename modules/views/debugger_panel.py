from __future__ import annotations
from ..typecheck import *

from ..import ui
from ..import dap
from . import css

from .breakpoints_panel import BreakpointsPanel

from .input_list_view import InputListView

if TYPE_CHECKING:
	from ..debugger import Debugger


class DebuggerPanel(ui.div):
	def __init__(self, debugger: Debugger, on_navigate_to_source: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__()
		self.debugger = debugger

		self.breakpoints = BreakpointsPanel(debugger.breakpoints, on_navigate_to_source)

		self.debugger.on_session_state_updated.add(lambda session, state: self.dirty())
		self.debugger.on_session_active.add(self.on_selected_session)
		self.debugger.on_session_added.add(self.on_selected_session)

		self.debugger.project.on_updated.add(self.dirty)
		self.last_active_adapter: None = None
		self.actions_tab = DebuggerActionsTab(debugger, css=None)

	def on_selected_session(self, session: dap.Session):
		self.last_active_adapter = session.adapter_configuration
		self.dirty()

	def render(self) -> ui.div.Children:
		# looks like
		# current status
		# breakpoints ...

		if self.debugger.is_active:
			self.last_active_adapter = self.debugger.active.adapter_configuration or self.last_active_adapter

		panel_items: list[ui.div] = []

		
		if self.debugger.is_active:
			session = self.debugger.active
			status = session.status
			if status:
				panel_items.append(ui.div(height=css.row_height)[
					ui.text(status, css=css.label_secondary)
				])

		if self.last_active_adapter:
			settings = self.last_active_adapter.settings(self.debugger)
			for setting in settings:
				panel_items.append(InputListView(setting))

			div = self.last_active_adapter.ui(self.debugger)
			if div: panel_items.append(div)

		panel_items.append(self.breakpoints)

		return [
			ui.div(height=css.header_height, width=30 - css.controls_panel.padding_width, css=css.controls_panel)[
				self.actions_tab
			],
			ui.div(width=30 - css.rounded_panel.padding_width, height=1000, css=css.panel)[
				panel_items
			],
		]


class DebuggerActionsTab(ui.span):
	def __init__(self, debugger: Debugger, css: ui.css|None = css.controls_panel) -> None:
		super().__init__(css=css)
		self.debugger = debugger

	def added(self) -> None:
		self.on_session_state_updated = self.debugger.on_session_state_updated.add(lambda session, state: self.dirty())
		self.on_session_removed = self.debugger.on_session_removed.add(lambda _: self.dirty())
		self.on_project_updated = self.debugger.project.on_updated.add(lambda: self.dirty())

	def removed(self) -> None:
		self.on_session_removed.dispose()
		self.on_session_state_updated.dispose()
		self.on_project_updated.dispose()

	def render(self) -> ui.div.Children:
		configuration_name = self.debugger.project.name
		items = []

	
		items = [
			DebuggerCommandButton(self.debugger.on_settings, ui.Images.shared.settings, 'Settings'),
			ui.spacer(1),
			DebuggerCommandButton(self.debugger.start, ui.Images.shared.play, f'Start: {configuration_name}' if configuration_name else 'Add/Select Configuration'),
			ui.spacer(1),
		]



		if self.debugger.is_stoppable():
			items.append(DebuggerCommandButton(self.debugger.stop, ui.Images.shared.stop, 'Stop'))
		else:
			items.append(DebuggerCommandButton(self.debugger.stop, ui.Images.shared.stop_disable, 'Stop (Disabled)'))


		name = self.debugger.project.name
		if len(name) > 11:
			name = name[:10] +  '…'
		else:
			name = name.ljust(11, ' ')

		if not self.debugger.is_active:
			items.append(
				ui.click(self.debugger.on_settings)[
					ui.spacer(1),
					ui.span(css=css.button_drop)[
						ui.text(name, css=css.label_secondary),
						# ui.spacer(1),
						ui.icon(ui.Images.shared.open, align_left=False)
					]
				])
		else:

			
			items.append(ui.spacer(1))

			if self.debugger.is_running():
				items.append(DebuggerCommandButton(self.debugger.pause, ui.Images.shared.pause, 'Pause'))
			elif self.debugger.is_paused():
				items.append(DebuggerCommandButton(self.debugger.resume, ui.Images.shared.resume, 'Continue'))
			else:
				items.append(DebuggerCommandButton(self.debugger.pause, ui.Images.shared.pause_disable, 'Pause (Disabled)'))

			items.append(ui.spacer(1))

			if self.debugger.is_paused():
				items.extend([
					DebuggerCommandButton(self.debugger.step_over, ui.Images.shared.down, 'Step Over'),
					ui.spacer(1),
					DebuggerCommandButton(self.debugger.step_out, ui.Images.shared.left, 'Step Out'),
					ui.spacer(1),
					DebuggerCommandButton(self.debugger.step_in, ui.Images.shared.right, 'Step In'),
				])
			else:
				items.extend([
					DebuggerCommandButton(self.debugger.step_over, ui.Images.shared.down_disable, 'Step Over (Disabled)'),
					ui.spacer(1),
					DebuggerCommandButton(self.debugger.step_out, ui.Images.shared.left_disable, 'Step Out (Disabled)'),
					ui.spacer(1),
					DebuggerCommandButton(self.debugger.step_in, ui.Images.shared.right_disable, 'Step In (Disabled)'),
				])
			items.append(ui.spacer(1))
		return items


class DebuggerCommandButton (ui.span):
	def __init__(self, callback: Callable[[], Any], image: ui.Image, title: str) -> None:
		super().__init__()

		self.image = image
		self.callback = callback
		self.title = title

	def render(self) -> ui.span.Children:
		return ui.click(self.callback, title=self.title)[
			ui.icon(self.image),
		]
