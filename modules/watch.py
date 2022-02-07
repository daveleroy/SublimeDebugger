from __future__ import annotations
from .typecheck import *

from .import core
from .import ui

from . import dap

import asyncio

class Watch:
	class Expression:
		def __init__(self, value: str):
			self.value = value
			self.message = ""
			self.evaluate_response: Optional[dap.Variable] = None
			self.on_updated: core.Event[None] = core.Event()

		def into_json(self) -> dap.Json:
			return {
				'value': self.value,
			}
		@staticmethod
		def from_json(json: dap.Json) -> Watch.Expression:
			return Watch.Expression(
				json['value'],
			)

	def __init__(self):
		self.expressions: list[Watch.Expression] = []
		self.on_updated: core.Event[None] = core.Event()
		self.on_added: core.Event[Watch.Expression] = core.Event()

	def load_json(self, json: list[dap.Json]):
		self.expressions = list(map(lambda j: Watch.Expression.from_json(j), json))
		self.on_updated.post()

	def into_json(self) -> list[dap.Json]:
		return list(map(lambda e: e.into_json(), self.expressions))

	def add(self, value: str) -> None:
		expression = Watch.Expression(value)
		self.expressions.append(expression)
		self.on_added(expression)
		self.on_updated.post()

	def add_command(self) -> None:
		def add(value: str):
			if value:
				self.add(value)

		ui.InputText(add, "Expression to watch").run()

	async def evaluate(self, session: dap.Session, frame: dap.StackFrame) -> None:
		results: list[Awaitable[dap.EvaluateResponse]] = []
		for expression in self.expressions:
			results.append(session.evaluate_expression(expression.value, "watch"))

		evaluations = await core.gather_results(*results)
		for expression, evaluation in zip(self.expressions, evaluations):
			self.evaluated(session, expression, evaluation)
		self.on_updated.post()

	async def evaluate_expression(self, session: dap.Session, expression: Watch.Expression) -> None:
		try:
			result = await session.evaluate_expression(expression.value, "watch")
			self.evaluated(session, expression, result)
		except dap.Error as result:
			self.evaluated(session, expression, result)
		self.on_updated.post()

	def evaluated(self, session: dap.Session, expression: Watch.Expression, evaluation: Union[Exception, dap.EvaluateResponse]):
		if isinstance(evaluation, Exception):
			expression.message = str(evaluation)
		else:
			expression.evaluate_response = dap.Variable.from_evaluate(session, expression.value, evaluation)

	def clear_session_data(self, session: dap.Session):
		for expression in self.expressions:
			expression.message = ''
			expression.evaluate_response = None
		self.on_updated.post()

	def edit(self, expression: Watch.Expression) -> ui.InputList:
		def remove():
			self.expressions.remove(expression)
			self.on_updated.post()

		return ui.InputList([
			ui.InputListItem(remove, "Remove"),
		])

	def edit_run(self, expression: Watch.Expression):
		self.edit(expression).run()

