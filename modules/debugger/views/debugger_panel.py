from ...typecheck import *
from ..adapter import Adapters
from ...import ui
from . import css
from ..import dap

from .input_list_view import InputListView

if TYPE_CHECKING:
	from ..debugger import Debugger


class DebuggerPanel(ui.div):
	def __init__(self, debugger: 'Debugger', breakpoints: ui.div) -> None:
		super().__init__()
		self.debugger = debugger
		self.name = ''
		self.breakpoints = breakpoints
		self.debugger.sessions.updated.add(lambda session, state: self.dirty())
		self.debugger.sessions.on_selected.add(self.on_selected_session)
		self.last_active_adapter = None

	def on_selected_session(self, session: dap.Session):
		self.last_active_adapter = session.adapter_configuration
		self.dirty()

	def render(self) -> ui.div.Children:
		buttons = [] #type: List[ui.span]

		items = [
			DebuggerCommandButton(self.debugger.on_settings, ui.Images.shared.settings),
			DebuggerCommandButton(self.debugger.on_play, ui.Images.shared.play),
		]


		if self.debugger.is_stoppable():
			items.append(DebuggerCommandButton(self.debugger.on_stop, ui.Images.shared.stop))
		else:
			items.append(DebuggerCommandButton(self.debugger.on_stop, ui.Images.shared.stop_disable))

		if self.debugger.is_running():
			items.append(DebuggerCommandButton(self.debugger.on_pause, ui.Images.shared.pause))
		elif self.debugger.is_paused():
			items.append(DebuggerCommandButton(self.debugger.on_resume, ui.Images.shared.resume))
		else:
			items.append(DebuggerCommandButton(self.debugger.on_pause, ui.Images.shared.pause_disable))

		if self.debugger.is_paused():
			items.extend([
				DebuggerCommandButton(self.debugger.on_step_over, ui.Images.shared.down),
				DebuggerCommandButton(self.debugger.on_step_out, ui.Images.shared.left),
				DebuggerCommandButton(self.debugger.on_step_in, ui.Images.shared.right),
			])
		else:
			items.extend([
				DebuggerCommandButton(self.debugger.on_step_over, ui.Images.shared.down_disable),
				DebuggerCommandButton(self.debugger.on_step_out, ui.Images.shared.left_disable),
				DebuggerCommandButton(self.debugger.on_step_in, ui.Images.shared.right_disable),
			])

		# looks like
		# current status
		# breakpoints ...

		panel_items = []
		if self.debugger.sessions.has_active:
			session = self.debugger.sessions.active
			status = session.status
			if status:
				panel_items.append(ui.div(height=css.row_height)[
					ui.text(status, css=css.label_secondary)
				])

		if self.last_active_adapter:
			settings = self.last_active_adapter.settings(self.debugger.sessions)
			for setting in settings:
				panel_items.append(InputListView(setting))


		panel_items.append(self.breakpoints)

		return [
			ui.div()[
				ui.div(height=css.header_height)[items],
				ui.div(width=27, height=1000, css=css.rounded_panel)[
					panel_items
				],
			]
		]


class DebuggerCommandButton (ui.span):
	def __init__(self, callback: Callable[[], None], image: ui.Image) -> None:
		super().__init__()

		self.image = image
		self.callback = callback

	def render(self) -> ui.span.Children:
		return [
			ui.span(css=css.padding)[
				ui.click(self.callback)[
					ui.icon(self.image),
				]
			]
		]
