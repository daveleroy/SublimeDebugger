from ..typecheck import *
from ..import core
from ..import ui

from .dap import types as dap
from .dap.variable import EvaluateReference, Variable

if TYPE_CHECKING:
	from .debugger_session import DebuggerSession

import asyncio

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

	def __init__(self):
		self.expressions = [] #type: List[Watch.Expression]
		self.on_updated = core.Event() #type: core.Event[None]
		self.on_added = core.Event() #type: core.Event[Watch.Expression]

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

	async def evaluate(self, session: 'DebuggerSession', frame: dap.StackFrame) -> None:
		results = [] #type: List[Awaitable[dap.EvaluateResponse]]
		for expression in self.expressions:
			results.append(session.evaluate_expression(expression.value, "watch"))

		evaluations = await asyncio.gather(*results, return_exceptions=True)
		for expression, evaluation in zip(self.expressions, evaluations):
			self.evaluated(session, expression, evaluation)
		self.on_updated()

	async def evaluate_expression(self, session: 'DebuggerSession', frame: dap.StackFrame, expression: 'Watch.Expression') -> None:
		try:
			result = await session.evaluate_expression(expression.value, "watch")
			self.evaluated(session, expression, result)
		except dap.Error as result:
			self.evaluated(session, expression, result)
		self.on_updated()

	def evaluated(self, session: 'DebuggerSession', expression: 'Watch.Expression', evaluation: Union[dap.Error, dap.EvaluateResponse]):
		if isinstance(evaluation, dap.Error):
				expression.message = str(evaluation)
		else:
			expression.evaluate_response = Variable(session, EvaluateReference(expression.value, evaluation))

	def clear_session_data(self, session: 'DebuggerSession'):
		for expression in self.expressions:
			expression.message = ''
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

