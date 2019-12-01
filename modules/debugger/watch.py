from ..typecheck import *
from ..import dap
from ..import core
from ..import ui
from ..components import css

from .variables import EvaluateReference, Variable, VariableComponent

if TYPE_CHECKING:
	from .debugger import DebuggerStateful

class Watch:
	class Expression:
		def __init__(self, value: str):
			self.value = value
			self.evaluate_response = None #type: Optional[Variable]
			self.message = ""
			self.on_updated = core.Event() #type: core.Event[None]

		def into_json(self) -> dict:
			return {
				'value': self.value,
			}
		@staticmethod
		def from_json(json: dict) -> 'Watch.Expression':
			return Watch.Expression(
				json['value'],
			)

	def __init__(self, on_added: Callable[['Watch.Expression'], None]):
		self.expressions = [] #type: List[Watch.Expression]
		self.on_updated = core.Event() #type: core.Event[None]
		self.on_added = on_added

	def load_json(self, json: list):
		self.expressions = list(map(lambda j: Watch.Expression.from_json(j), json))
		self.on_updated()

	def into_json(self) -> list:
		return list(map(lambda e: e.into_json(), self.expressions))

	def add(self, value: str) -> None:
		expression = Watch.Expression(value)
		self.expressions.append(expression)
		self.on_added(expression)
		self.on_updated()

	def add_command(self) -> None:
		def add(value: str):
			if value:
				self.add(value)

		ui.InputText(add, "Expression to watch").run()

	@core.coroutine
	def evaluate(self, debugger: 'DebuggerStateful', frame: dap.StackFrame) -> core.awaitable[None]:
		results = [] #type: List[core.awaitable[dap.EvaluateResponse]]
		for expression in self.expressions:
			results.append(debugger.adapter.Evaluate(expression.value, frame, "watch"))

		from ..libs import asyncio
		evaluations = yield from asyncio.gather(*results, return_exceptions=True)
		for expression, evaluation in zip(self.expressions, evaluations):
			self.evaluated(debugger, expression, evaluation)
		self.on_updated()

	@core.coroutine
	def evaluate_expression(self, debugger: 'DebuggerStateful', frame: dap.StackFrame, expression: 'Watch.Expression') -> core.awaitable[None]:
		try:
			result = yield from debugger.adapter.Evaluate(expression.value, frame, "watch")
			self.evaluated(debugger, expression, result)
		except dap.Error as result:
			self.evaluated(debugger, expression, result)
		self.on_updated()

	def evaluated(self, debugger: 'DebuggerStateful', expression: 'Watch.Expression', evaluation: Union[dap.Error, dap.EvaluateResponse]):
		if isinstance(evaluation, dap.Error):
				expression.message = str(evaluation)
		else:
			expression.evaluate_response = Variable(debugger, EvaluateReference(expression.value, evaluation))

	def clear_session_data(self):
		for expression in self.expressions:
			expression.message = None
			expression.evaluate_response = None
		self.on_updated()
	
	def edit(self, expression: 'Watch.Expression') -> ui.InputList:
		def remove():
			self.expressions.remove(expression)
			self.on_updated()

		return ui.InputList([
			ui.InputListItem(remove, "Remove"),
		])

	def edit_run(self, expression: 'Watch.Expression'):
		self.edit(expression).run()

class WatchView(ui.div):
	def __init__(self, provider: Watch):
		super().__init__()
		self.provider = provider

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.provider.on_updated.add(self.dirty)
	
	def removed(self):
		self.on_updated_handle.dispose()

	def render(self) -> ui.div.Children:
		items = []
		for expresion in self.provider.expressions:
			items.append(WatchExpressionView(expresion, on_edit_not_available=self.provider.edit_run))
		return [
			ui.div()[
				items
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

	def render(self) -> ui.div.Children:
		if self.expression.evaluate_response:
			component = VariableComponent(self.expression.evaluate_response)
			self.expression.evaluate_response.on_dirty = component.dirty
			return [component]

		return [
			ui.div(height=3)[
				ui.click(lambda: self.on_edit_not_available(self.expression))[
					ui.text(self.expression.value, css=css.label_secondary),
					ui.text("not available", css=css.label_secondary_padding),
				]
			]
		]
