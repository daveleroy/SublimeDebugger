from ..views.variables import WatchExpressionView
from ..views.variable import VariableView
from ..command import ActionElement


class VariableCopyValue(ActionElement):
	name = 'Copy Value'
	key = 'variable_copy_value'
	view = VariableView

	def action(self, debugger, element: VariableView):
		element.copy_value()


class VariableCopyAsExpression(ActionElement):
	name = 'Copy as Expression'
	key = 'variable_copy_expression'
	element = VariableView

	def action(self, debugger, element: VariableView):
		element.copy_expr()


class VariableAddToWatch(ActionElement):
	name = 'Add To Watch'
	key = 'variable_add_to_watch'
	element = VariableView

	def action(self, debugger, element: VariableView):
		element.add_watch()


class WatchRemoveExpression(ActionElement):
	name = 'Remove Expression'
	key = 'watch_remove_expression'
	element = WatchExpressionView

	def action(self, debugger, element: WatchExpressionView):
		debugger.watch.remove(element.expression)


class WatchRemoveAllExpression(ActionElement):
	name = 'Remove All Expressions'
	key = 'watch_remove_all_expressions'
	element = WatchExpressionView

	def action(self, debugger, element: WatchExpressionView):
		debugger.watch.remove_all()
