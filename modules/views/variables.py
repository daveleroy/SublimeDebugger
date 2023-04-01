from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from ..import ui
from ..import dap

from ..watch import Watch
from .variable import VariableView
from . import css
from .tabbed import TabbedView

if TYPE_CHECKING:
	from ..debugger import Debugger


class VariablesTabbedView (TabbedView):
	def __init__(self, debugger: Debugger):
		super().__init__('Variables')
		self.watch_view = WatchView(debugger)
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

	def on_updated(self, session: dap.Session):
		self.dirty()

	def render(self):
		session = self.debugger.session
		if not session:
			return

		variables = [VariableView(self.debugger, variable) for variable in session.variables]
		if variables:
			variables[0].set_expanded()

		return variables


class WatchView(ui.div):
	def __init__(self, debugger: Debugger) -> None:
		super().__init__()
		self.debugger = debugger
		self.open = self.debugger.watch.expressions

	def added(self):
		self.on_updated_handle = self.debugger.watch.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def toggle_expand(self):
		self.open = not self.open
		self.dirty()

	def render_children(self):
		if not self.debugger.watch.expressions:
			return ui.div(height=css.row_height)[
				ui.spacer(3),
				ui.text('zero items …', css=css.secondary)
			]

		return [WatchExpressionView(self.debugger, expresion, on_edit_not_available=self.debugger.watch.edit_run) for expresion in self.debugger.watch.expressions]

	def render(self) -> ui.div.Children:

		header = ui.div(height=css.row_height)[
			ui.icon(ui.Images.shared.open if self.open else ui.Images.shared.close, on_click=self.toggle_expand),
			ui.text('Watch', css=css.secondary),
			ui.spacer(),
			ui.text('add', css=css.secondary, on_click=self.debugger.add_watch_expression)
		]

		if not self.open:
			return header

		return [
			header,
			ui.div(css=css.table_inset)[
				self.render_children()
			]
		]

class WatchExpressionView(ui.div):
	def __init__(self, debugger: Debugger, expression: Watch.Expression, on_edit_not_available: Callable[[Watch.Expression], None]):
		super().__init__()
		self.debugger = debugger
		self.expression = expression
		self.on_edit_not_available = on_edit_not_available

	def added(self):
		self.on_updated_handle = self.expression.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def render(self):
		if self.expression.evaluate_response:
			component = VariableView(self.debugger, self.expression.evaluate_response)
			return [component]

		return ui.div(height=css.row_height)[
			ui.spacer(3),
			ui.span(on_click=lambda: self.on_edit_not_available(self.expression)) [
				ui.text(self.expression.value, css=css.secondary),
				ui.spacer(1),
				ui.text("not available", css=css.label),
			]
		]
