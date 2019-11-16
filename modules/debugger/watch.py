from ..typecheck import *
from ..import dap
from ..import core
from ..import ui
from ..components.variable_component import EvaluateVariable, VariableStateful, VariableStatefulComponent

if TYPE_CHECKING:
	from .debugger import DebuggerStateful

class Watch:
	class Expression:
		def __init__(self, value: str):
			self.value = value
			self.evaluate_response = None #type: Optional[VariableStateful]
			self.message = ""
			self.on_updated = core.Event() #type: core.Event[None]

		def into_json(self) -> dict:
			return {
				'value': self.value,
			}
		@staticmethod
		def from_json(json: dict) -> 'Watch.Expression':
			return Watch.Expression (
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
	def evaluate(self, client: dap.Client, frame: dap.StackFrame) -> core.awaitable[None]:
		results = [] #type: List[core.awaitable[dap.EvaluateResponse]]
		for expression in self.expressions:
			results.append(client.Evaluate(expression.value, frame, "watch"))

		from ..libs import asyncio
		evaluations = yield from asyncio.gather(*results, return_exceptions=True)
		for expression, evaluation in zip(self.expressions, evaluations):
			self.evaluated(client, expression, evaluation)
		self.on_updated()

	@core.coroutine
	def evaluate_expression(self, client: dap.Client, frame: dap.StackFrame, expression: 'Watch.Expression') -> core.awaitable[None]:
		try:
			result = yield from client.Evaluate(expression.value, frame, "watch")
			self.evaluated(client, expression, result)
		except dap.Error as result:
			self.evaluated(client, expression, result)
		self.on_updated()

	def evaluated(self, client: dap.Client, expression: 'Watch.Expression', evaluation: Union[dap.Error, dap.EvaluateResponse]):
		if isinstance(evaluation, dap.Error):
				expression.message = str(evaluation)
		else:
			evaluate_variable = EvaluateVariable(client, expression.value, evaluation)
			def on_edit(variable: EvaluateVariable):
				if variable is expression.evaluate_response:
					self.edit(expression).run()

			expression.evaluate_response = VariableStateful(evaluate_variable, None, on_edit=on_edit)

	def clear_session_data(self):
		for expression in self.expressions:
			expression.message = None
			expression.evaluate_response = None

	def edit(self, expression: 'Watch.Expression') -> ui.InputList:
		def remove():
			self.expressions.remove(expression)
			self.on_updated()

		return ui.InputList([
			ui.InputListItem(remove, "Remove"),
		])

	def edit_run(self, expression: 'Watch.Expression'):
		self.edit(expression).run()

class WatchView(ui.Block):
	def __init__(self, provider: Watch):
		super().__init__()
		self.provider = provider

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.provider.on_updated.add(self.dirty)
	
	def removed(self):
		self.on_updated_handle.dispose()

	def render(self) -> ui.Panel.Children:
		items = []
		for expresion in self.provider.expressions:
			items.append(WatchExpressionView(expresion, on_edit_not_available=self.provider.edit_run))
		return [
			ui.Table(items=items)
		]

class WatchExpressionView(ui.Block):
	def __init__(self, expression: Watch.Expression, on_edit_not_available: Callable[[Watch.Expression], None]):
		super().__init__()
		self.expression = expression
		self.on_edit_not_available = on_edit_not_available

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.expression.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def render(self) -> ui.Block.Children:
		if self.expression.evaluate_response:
			component = VariableStatefulComponent(self.expression.evaluate_response)
			self.expression.evaluate_response.on_dirty = component.dirty
			return [component]

		return [
			ui.block(
				ui.Button(lambda: self.on_edit_not_available(self.expression), [
					ui.Label(self.expression.value, padding_left=0.5, padding_right=1), 
					ui.Label("not available", color="secondary")
				])
			)
		]
