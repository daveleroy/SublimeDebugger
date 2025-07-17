from __future__ import annotations
from asyncio import Future
from typing import TYPE_CHECKING

from dataclasses import dataclass

import os

from ..import core
import sublime


from .import api

if TYPE_CHECKING:
	from .session import Session

@dataclass
class SourceLocation:
	source: api.Source
	line: int|None = None
	column: int|None = None

	line_regex: str|None = None

	@staticmethod
	def from_path(file: str, line: int|None = None, column: int|None = None, line_regex: str|None = None) -> SourceLocation:
		return SourceLocation(api.Source(os.path.basename(file), file), line, column, line_regex)

	@property
	def name(self) -> str:
		name = os.path.basename(self.source.name or '??')
		if self.column and self.line:
			return f'{name}@{self.line}:{self.column}'
		if self.line:
			return f'{name}@{self.line}'

		return name

	def open_file(self):
		sublime.active_window().run_command('open_file', {'file': f'{self.source.path}:{(self.line or 0) + 1}', 'encoded_position': True})


class Variable:
	def __init__(self, session: Session, name: str, value: str|None, variablesReference: int|None, containerVariablesReference: int|None = None, evaluateName: str|None = None, memoryReference: str|None = None) -> None:
		self.session = session
		self.name = name
		self.evaluateName = evaluateName
		self.value = value
		self.variablesReference = variablesReference
		self.containerVariablesReference = containerVariablesReference
		self.memoryReference = memoryReference
		self.fetched: Future[list[Variable]]|None = None


	@staticmethod
	def from_variable(session: Session, containerVariablesReference: int, variable: api.Variable):
		return Variable(
			session,
			variable.name,
			variable.value,
			variable.variablesReference,
			containerVariablesReference,
			variable.evaluateName,
			variable.memoryReference,
		)

	@staticmethod
	def from_scope(session: Session, scope: api.Scope):
		return Variable(
			session,
			scope.name,
			None,
			scope.variablesReference,
		)

	@staticmethod
	def from_evaluate(session: Session, name: str, evaluate: api.EvaluateResponse):
		return Variable(
			session,
			name,
			evaluate.result,
			evaluate.variablesReference,
		)

	async def fetch(self):
		assert self.variablesReference
		return await self.session.get_variables(self.variablesReference)

	async def children(self) -> list[Variable]:
		if not self.has_children:
			return []

		if not self.fetched:
			self.fetched = core.run(self.fetch())

		children = await self.fetched
		return children

	@property
	def has_children(self) -> bool:
		return bool(self.variablesReference)
