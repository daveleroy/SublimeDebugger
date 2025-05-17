from __future__ import annotations
from typing import TYPE_CHECKING, Callable


from .. import core
from .. import ui
from .. import dap
from . import css

from .breakpoints import BreakpointsView
from .tabbed import TabbedView

if TYPE_CHECKING:
	from ..debugger import Debugger


class DebuggerTabbedView(TabbedView, core.Dispose):
	def __init__(self, debugger: Debugger, on_navigate_to_source: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__('Debugger')

		self.debugger = debugger

		self.breakpoints = BreakpointsView(debugger.breakpoints, on_navigate_to_source)

		self.last_adapter: dap.Adapter | None = None

		# self.process = ProcessView(debugger)

	def added(self) -> None:
		self.dispose_add(
			self.debugger.on_session_updated.add(lambda session: self.dirty()),
			self.debugger.on_session_active.add(self.on_selected_session),
			self.debugger.on_session_added.add(self.on_selected_session),
			self.debugger.project.on_updated.add(self.dirty),
		)

	def removed(self) -> None:
		self.dispose()

	def header(self, is_selected): ...

	def on_selected_session(self, session: dap.Session):
		self.last_adapter = session.adapter
		self.dirty()

	def render(self):
		# looks like
		# current status
		# breakpoints ...

		if session := self.debugger.session:
			self.last_adapter = session.adapter

			if status := session.state.status:
				with ui.div(height=css.row_height):
					ui.text(status, css=css.secondary)

		if self.last_adapter:
			self.last_adapter.ui(self.debugger)

		self.breakpoints.append_stack()
