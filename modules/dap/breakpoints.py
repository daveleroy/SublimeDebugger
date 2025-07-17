from __future__ import annotations
from typing import Protocol

from .error import Error

from .session import Session

from ..import ui
from .. import core

from . import api

from .breakpoint import Breakpoint
from .breakpoint_data import DataBreakpoints, DataBreakpoint
from .breakpoint_function import FunctionBreakpoints, FunctionBreakpoint
from .breakpoint_source import SourceBreakpoints, SourceBreakpoint
from .breakpoint_exception_filters import ExceptionBreakpointsFilters, ExceptionBreakpointsFilter

class IBreakpoint (Protocol):
	@property
	def image(self) -> ui.Image: ...
	@property
	def tag(self) -> str|None: ...
	@property
	def name(self) -> str: ...
	@property
	def description(self) -> str|None: ...

class Breakpoints:
	def __init__(self) -> None:
		self.data = DataBreakpoints()
		self.function = FunctionBreakpoints()
		self.filters = ExceptionBreakpointsFilters()
		self.source = SourceBreakpoints()

	def dispose(self) -> None:
		self.source.dispose()

	def set_breakpoint_result(self, breakpoint: Breakpoint, session: Session, result: api.Breakpoint) -> None:
		if isinstance(breakpoint, DataBreakpoint):
			self.data.set_breakpoint_result(breakpoint, session, result)
		elif isinstance(breakpoint, FunctionBreakpoint):
			self.function.set_breakpoint_result(breakpoint, session, result)
		elif isinstance(breakpoint, SourceBreakpoint):
			self.source.set_breakpoint_result(breakpoint, session, result)
		else:
			raise Error('Unsupprted Breakpoint type)')

	def remove_all(self):
		self.source.remove_all()
		self.data.remove_all()
		self.function.remove_all()

	def clear_breakpoint_result(self, session: Session) -> None:
		self.data.clear_breakpoint_result(session)
		self.function.clear_breakpoint_result(session)
		self.source.clear_breakpoint_result(session)

	def load_from_json(self, json: core.JSON) -> None:
		self.source.load_json(json.get('source', []))
		self.function.load_json(json.get('function', []))
		self.filters.load_json(json.get('filters', []))

	def into_json(self) -> core.JSON:
		return core.JSON({
			'source': self.source.into_json(),
			'function': self.function.into_json(),
			'filters': self.filters.into_json(),
		})
