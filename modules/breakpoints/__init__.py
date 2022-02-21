from __future__ import annotations
from ..typecheck import *
from ..import ui

from .. import dap

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

	def clear_session_data(self) -> None:
		self.data.clear_session_data()
		self.function.clear_session_data()
		self.source.clear_session_data()

	def load_from_json(self, json: dap.Json) -> None:
		self.source.load_json(json.get('source', []))
		self.function.load_json(json.get('function', []))
		self.filters.load_json(json.get('filters', []))

	def into_json(self) -> dap.Json:
		return {
			'source': self.source.into_json(),
			'function': self.function.into_json(),
			'filters': self.filters.into_json(),
		}
