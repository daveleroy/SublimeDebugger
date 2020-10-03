from __future__ import annotations
from dataclasses import dataclass

import os

from ...typecheck import *
from ...import core
from . import types as dap

if TYPE_CHECKING:
	from .session import Session

@dataclass
class SourceLocation:
	source: dap.Source
	line: Optional[int] = None
	column: Optional[int] = None

	@staticmethod
	def from_path(file: str, line: Optional[int], column: Optional[int]) -> SourceLocation:
		return SourceLocation(dap.Source(os.path.basename(file), file), line, column)

	@property
	def name(self) -> str:
		if self.column and self.line:
			return f'{self.source.name}@{self.line}:{self.column}'
		if self.line:
			return f'{self.source.name}@{self.line}'

		return self.source.name or "??"

class VariableReference (Protocol):
	@property
	def name(self) -> str:
		...
	@property
	def value(self) -> str:
		...
	@property
	def variablesReference(self) -> int:
		...

class EvaluateReference(VariableReference):
	def __init__(self, name: str, response: dap.EvaluateResponse):
		self._response = response
		self._name = name
	@property
	def variablesReference(self) -> int:
		return self._response.variablesReference
	@property
	def name(self) -> str:
		return self._name
	@property
	def value(self) -> str:
		return self._response.result

class ScopeReference(VariableReference):
	def __init__(self, scope: dap.Scope):
		self.scope = scope
	@property
	def variablesReference(self) -> int:
		return self.scope.variablesReference
	@property
	def name(self) -> str:
		return self.scope.name
	@property
	def value(self) -> str:
		return ""

class Variable:
	def __init__(self, session: Session, reference: VariableReference) -> None:
		self.session = session
		self.reference = reference
		self.fetched = None #type: Optional[core.future]

	@property
	def name(self) -> str:
		return self.reference.name

	@property
	def value(self) -> str:
		return self.reference.value

	async def fetch(self):
		return await self.session.get_variables(self.reference.variablesReference)

	async def children(self) -> List[Variable]:
		if not self.has_children:
			return []

		if not self.fetched:
			self.fetched = core.run(self.fetch())
		children = await self.fetched
		return children

	@property
	def has_children(self) -> bool:
		return self.reference.variablesReference != 0

