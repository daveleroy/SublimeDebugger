from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from functools import partial

from .. import ui
from .. import core
from .. import dap
from . import css
from .tabbed import TabbedView

if TYPE_CHECKING:
	from ..debugger import Debugger


class SourcesTabbedView(TabbedView, core.Dispose):
	def __init__(self, debugger: Debugger, on_click: Callable[[dap.SourceLocation], None]):
		super().__init__('Sources')
		self.debugger = debugger
		self.on_click = on_click
		self._visible = False


	def added(self) -> None:
		self.dispose_add(
			self.debugger.on_session_sources_updated.add(self.updated),
			self.debugger.on_session_removed.add(self.updated),
		)

	def removed(self) -> None:
		self.dispose()

	def visible(self) -> bool:
		return self._visible

	def updated(self, session: dap.Session):
		visible = False
		for session in self.debugger.sessions:
			if session.sources:
				visible = True
				break

		if visible != self._visible:
			self.dirty_header()

		if visible:
			self.dirty()

	def on_clicked_source(self, source: dap.Source):
		self.on_click(dap.SourceLocation(source, None, None))

	def render(self):
		for session in self.debugger.sessions:
			for source in session.sources.values():
				with ui.div(height=css.row_height):
					ui.text(source.path or source.name or '<no source name>', css=css.secondary, on_click=partial(self.on_clicked_source, source))
