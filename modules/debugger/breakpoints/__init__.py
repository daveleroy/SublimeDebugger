from ...typecheck import *
from ... import core
from ... import ui

from ..dap import types as dap

from .data_breakpoints import DataBreakpoints, DataBreakpoint
from .function_breakpoints import FunctionBreakpoints, FunctionBreakpoint
from .source_breakpoints import SourceBreakpoints, SourceBreakpoint
from .exception_filters import ExceptionBreakpointsFilters, ExceptionBreakpointsFilter


class IBreakpoint (Protocol):
	@property
	def image(self) -> ui.Image:
		...
	@property
	def tag(self) -> Optional[str]:
		...
	@property
	def name(self) -> str:
		...

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

	def load_from_json(self, json) -> None:
		self.source.load_json(json.get('source', []))
		self.function.load_json(json.get('function', []))
		self.filters.load_json(json.get('filters', []))

	def into_json(self) -> dict:
		return {
			'source': self.source.into_json(),
			'function': self.function.into_json(),
			'filters': self.filters.into_json(),
		}
