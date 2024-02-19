from __future__ import annotations
from typing import Protocol

from ..import ui
from .. import dap
from .. import core

from .breakpoint import Breakpoint
from .data_breakpoints import DataBreakpoints, DataBreakpoint
from .function_breakpoints import FunctionBreakpoints, FunctionBreakpoint
from .source_breakpoints import SourceBreakpoints, SourceBreakpoint
from .exception_filters import ExceptionBreakpointsFilters, ExceptionBreakpointsFilter

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

	def set_breakpoint_result(self, breakpoint: Breakpoint, session: dap.Session, result: dap.Breakpoint) -> None:
		if isinstance(breakpoint, DataBreakpoint):
			self.data.set_breakpoint_result(breakpoint, session, result)
		elif isinstance(breakpoint, FunctionBreakpoint):
			self.function.set_breakpoint_result(breakpoint, session, result)
		elif isinstance(breakpoint, SourceBreakpoint):
			self.source.set_breakpoint_result(breakpoint, session, result)
		else:
			raise core.Error('Unsupprted Breakpoint type)')

	def remove_all(self):
		self.source.remove_all()
		self.data.remove_all()
		self.function.remove_all()

	def clear_breakpoint_result(self, session: dap.Session) -> None:
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
