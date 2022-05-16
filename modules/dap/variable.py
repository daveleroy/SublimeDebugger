from __future__ import annotations
from dataclasses import dataclass

import os

from ..typecheck import *
from ..import core
from .import dap

if TYPE_CHECKING:
	from .session import Session

@dataclass
class SourceLocation:
	source: dap.Source
	line: int|None = None
	column: int|None = None

	@staticmethod
	def from_path(file: str, line: int|None, column: int|None) -> SourceLocation:
		return SourceLocation(dap.Source(os.path.basename(file), file), line, column)

	@property
	def name(self) -> str:
		name = os.path.basename(self.source.name or '??')
		if self.column and self.line:
			return f'{name}@{self.line}:{self.column}'
		if self.line:
			return f'{name}@{self.line}'

		return name


class Variable:
	def __init__(self, session: Session, name: str, value: str|None, variablesReference: int|None, containerVariablesReference: int|None = None, evaluateName: str|None = None, memoryReference: str|None = None) -> None:
		self.session = session
		self.name = name
		self.evaluateName = evaluateName
		self.value = value
		self.variablesReference = variablesReference
		self.containerVariablesReference = containerVariablesReference
		self.memoryReference = memoryReference
		self.fetched: core.Future[list[Variable]]|None = None
		

	@staticmethod
	def from_variable(session: Session, containerVariablesReference: int, variable: dap.Variable):
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
	def from_scope(session: Session, scope: dap.Scope):
		return Variable(
			session,
			scope.name,
			None,			
			scope.variablesReference,
		)

	@staticmethod
	def from_evaluate(session: Session, name: str, evaluate: dap.EvaluateResponse):
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

