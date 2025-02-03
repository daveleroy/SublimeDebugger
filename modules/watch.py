from __future__ import annotations
from dataclasses import dataclass
from typing import Awaitable
from . import core
from . import ui
from . import dap


@dataclass
class WatchExpression:
	value: str
	message = ''
	evaluate_response: dap.Variable | None = None
	on_updated = core.Event[None]()

	def into_json(self) -> core.JSON:
		return core.JSON(
			{
				'value': self.value,
			}
		)

	@staticmethod
	def from_json(json: core.JSON) -> WatchExpression:
		return WatchExpression(
			json['value'],
		)


class Watch(core.Dispose):
	on_updated = core.Event[None]()
	expressions: list[WatchExpression] = []

	def __init__(self, debugger: dap.Debugger):
		self.debugger = debugger

		self.dispose_add(debugger.on_session_thread_or_frame_updated.add(self._on_thread_or_frame_updated))

	def _on_thread_or_frame_updated(self, session: dap.Session):
		if session.selected_frame:
			self.evaluate(session, session.selected_frame)

	def load_json(self, json: list[core.JSON]):
		self.expressions = list(map(lambda j: WatchExpression.from_json(j), json))
		self.on_updated()

	def into_json(self) -> list[core.JSON]:
		return list(map(lambda e: e.into_json(), self.expressions))

	def add(self, value: str) -> None:
		expression = WatchExpression(value)
		self.expressions.append(expression)
		self.on_updated()

		# just re-evaluate all the expressions since we just added one
		for session in self.debugger.sessions:
			if session.selected_frame:
				self.evaluate(session, session.selected_frame)

	@core.run
	async def add_command(self) -> None:
		def add(value: str):
			if value:
				self.add(value)

		await ui.InputText(add, 'Expression to watch')

	@core.run
	async def evaluate(self, session: dap.Session, frame: dap.StackFrame) -> None:
		results: list[Awaitable[dap.EvaluateResponse]] = []
		for expression in self.expressions:
			results.append(session.evaluate_expression(expression.value, 'watch'))

		evaluations = await core.gather_results(*results)
		for expression, evaluation in zip(self.expressions, evaluations):
			self.evaluated(session, expression, evaluation)
		self.on_updated()

	async def evaluate_expression(self, session: dap.Session, expression: WatchExpression) -> None:
		try:
			result = await session.evaluate_expression(expression.value, 'watch')
			self.evaluated(session, expression, result)
		except dap.Error as result:
			self.evaluated(session, expression, result)
		self.on_updated()

	def evaluated(self, session: dap.Session, expression: WatchExpression, evaluation: Exception | dap.EvaluateResponse):
		if isinstance(evaluation, Exception):
			expression.message = str(evaluation)
		else:
			expression.evaluate_response = dap.Variable.from_evaluate(session, expression.value, evaluation)

	def clear_session_data(self, session: dap.Session):
		for expression in self.expressions:
			expression.message = ''
			expression.evaluate_response = None
		self.on_updated()

	def remove(self, expression: WatchExpression):
		self.expressions.remove(expression)
		self.on_updated()

	def remove_all(self):
		self.expressions.clear()
		self.on_updated()
