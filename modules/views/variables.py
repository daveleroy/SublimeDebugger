from __future__ import annotations
from typing import TYPE_CHECKING


from .. import ui
from .. import dap
from .. import core

from ..watch import WatchExpression
from .variable import VariableView
from . import css
from .tabbed import TabbedView

if TYPE_CHECKING:
	from ..debugger import Debugger


class VariablesTabbedView(TabbedView):
	def __init__(self, debugger: Debugger):
		super().__init__('Variables')
		self.watch_view = WatchView(debugger)
		self.variables_view = VariablesView(debugger)

	def header(self, is_selected: bool): ...

	def render(self):
		self.watch_view.append_stack()
		self.variables_view.append_stack()


class VariablesView(ui.div):
	def __init__(self, debugger: Debugger):
		super().__init__()
		self.debugger = debugger
		self.debugger.on_session_variables_updated.add(self.on_updated)
		self.debugger.on_session_removed.add(self.on_updated)

	def on_updated(self, session: dap.Session):
		self.dirty()

	def render(self):
		with ui.div():
			ui.text('Variables')

		session = self.debugger.session
		if not session:
			with ui.div():
				ui.spacer(3)
				ui.text('No debug session', css.secondary)

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

	def added(self):
		self.on_updated_handle = self.debugger.watch.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def render(self):
		from ..commands.commands import AddWatchExpression

		with ui.div():
			ui.text('Watched')
			ui.spacer()
			ui.text('add', css=css.button, on_click=lambda: self.debugger.run_action(AddWatchExpression))

		with ui.div():
			if not self.debugger.watch.expressions:
				with ui.div():
					ui.spacer(3)
					ui.text('No watched expressions', css=css.secondary)

			for expresion in self.debugger.watch.expressions:
				WatchExpressionView(self.debugger, expresion)


class WatchExpressionView(ui.div):
	def __init__(self, debugger: Debugger, expression: WatchExpression):
		super().__init__()
		self.debugger = debugger
		self.expression = expression

	def added(self):
		self.on_updated_handle = self.expression.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def render(self):
		if self.expression.evaluate_response:
			VariableView(self.debugger, self.expression.evaluate_response, on_remove=lambda: self.debugger.watch.remove(self.expression))
		else:
			with ui.div():
				ui.spacer(3)
				with ui.span(on_click=self.show_remove_menu):
					ui.text(self.expression.value, css=css.secondary)
					ui.spacer(1)
					ui.text('not available', css=css.label)

	@core.run
	async def show_remove_menu(self):
		await ui.InputList('Remove')[ui.InputListItem(lambda: self.debugger.watch.remove(self.expression), 'Remove')]
