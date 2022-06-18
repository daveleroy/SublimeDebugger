from __future__ import annotations
from ..typecheck import *

from ..import ui
from ..import dap

from ..watch import Watch
from .variable import VariableComponent
from . import css
from .tabbed_panel import Panel

if TYPE_CHECKING:
	from ..debugger import Debugger

class VariablesPanel (Panel):
	def __init__(self, debugger: Debugger):
		super().__init__('Variables')
		self.watch_view = WatchView(debugger.watch)
		self.variables_view = VariablesView(debugger)

	def render(self) -> ui.div.Children:
		return [
			self.watch_view,
			self.variables_view,
		]


class VariablesView (ui.div):
	def __init__(self, debugger: Debugger):
		super().__init__()
		self.debugger = debugger
		self.debugger.on_session_variables_updated.add(self.on_updated)
		self.debugger.on_session_removed.add(self.on_updated)
		self.variables = []

	def on_updated(self, session: dap.Session):
		if self.debugger.session:
			self.variables = [
				VariableComponent(self.debugger, variable) for variable in self.debugger.session.variables
			]
			self.variables and self.variables[0].set_expanded()
		else:
			self.variables = []

		self.dirty()

	def render(self):
		session = self.debugger.session
		if not session:
			return

		variables = [VariableComponent(self.debugger, variable) for variable in session.variables]
		if variables:
			variables[0].set_expanded()

		return variables


class WatchView(ui.div):
	def __init__(self, watch: Watch):
		super().__init__()
		self.watch = watch
		self.open = True

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.watch.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def toggle_expand(self):
		self.open = not self.open
		self.dirty()

	def render(self) -> ui.div.Children:
		if not self.watch.expressions:
			return None

		header = ui.div(height=css.row_height)[
			ui.click(self.toggle_expand)[
				ui.icon(ui.Images.shared.open if self.open else ui.Images.shared.close)
			],
			ui.text('Watch', css=css.label_secondary)
		]
		if not self.open:
			return header

		return [
			header,
			ui.div(css=css.table_inset)[
				[WatchExpressionView(expresion, on_edit_not_available=self.watch.edit_run) for expresion in self.watch.expressions]
			]
		]

class WatchExpressionView(ui.div):
	def __init__(self, expression: Watch.Expression, on_edit_not_available: Callable[[Watch.Expression], None]):
		super().__init__()
		self.expression = expression
		self.on_edit_not_available = on_edit_not_available

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.expression.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def render(self):
		if self.expression.evaluate_response:
			component = VariableComponent(self.expression.evaluate_response)
			return [component]

		return [
			ui.div(height=css.row_height, css=css.padding_left)[
				ui.click(lambda: self.on_edit_not_available(self.expression))[
					ui.text(self.expression.value, css=css.label_secondary),
					ui.spacer(1),
					ui.text("not available", css=css.label),
				]
			]
		]
