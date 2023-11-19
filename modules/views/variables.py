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

	def render(self):
		self.watch_view.append_stack()
		self.variables_view.append_stack()


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

		expand = True
		for variable in session.variables:
			view = VariableView(self.debugger, variable)
			if expand:
				view.set_expanded()
				expand = False


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

	def render(self):
		with ui.div(height=css.row_height):
			ui.icon(ui.Images.shared.open if self.open else ui.Images.shared.close, on_click=self.toggle_expand)
			ui.text('Watch', css=css.secondary)
			ui.spacer()
			ui.text('add', css=css.secondary, on_click=self.debugger.add_watch_expression)

		if not self.open:
			return

		with ui.div(css=css.table_inset):
			if not self.debugger.watch.expressions:
				with ui.div(height=css.row_height):
					ui.spacer(3)
					ui.text('zero items …', css=css.secondary)

			for expresion in self.debugger.watch.expressions:
				WatchExpressionView(self.debugger, expresion, on_edit_not_available=self.debugger.watch.edit_run)



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
			VariableView(self.debugger, self.expression.evaluate_response)
			return

		with ui.div(height=css.row_height):
			ui.spacer(3)
			with ui.span(on_click=lambda: self.on_edit_not_available(self.expression)):
				ui.text(self.expression.value, css=css.secondary)
				ui.spacer(1)
				ui.text("not available", css=css.label)
