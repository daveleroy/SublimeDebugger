from __future__ import annotations
from ..typecheck import *

from ..import ui
from .. import dap
from .tabbed_panel import Panel
from . import css

if TYPE_CHECKING:
	from ..debugger import Debugger

class SourcesPanel(Panel):
	def __init__(self, debugger: Debugger, on_click: Callable[[dap.SourceLocation], None]):
		super().__init__('Sources')
		self.debugger = debugger
		self.on_click = on_click
		self._visible = False

		debugger.on_session_sources_updated.add(self.updated)
		debugger.on_session_removed.add(self.updated)

	def visible(self) -> bool:
		return self._visible

	def updated(self, session: dap.Session):
		self._visible = False
		for session in self.debugger.sessions:
			if session.sources:
				self._visible = True
				break

		self.dirty_header()
		self.dirty()

	def render(self):
		items: list[SourceView] = []
		for session in self.debugger.sessions:
			for source in session.sources.values():
				items.append(SourceView(source, self.on_click))

		return [
			ui.div()[items]
		]


class SourceView(ui.div):
	def __init__(self, source: dap.Source, on_click: Callable[[dap.SourceLocation], None]):
		super().__init__()
		self.source = source
		self.on_click = on_click

	def render(self):
		items = [
			ui.div(height=css.row_height)[
				ui.align()[
					ui.click(lambda: self.on_click(dap.SourceLocation(self.source, None, None)))[
						ui.text(self.source.path or self.source.name or "<no source name>", css=css.label_secondary)
					]
				]
			]
		]
		# for sub_source in self.source.sources:
		# 	items.append(SourceView(sub_source, self.on_click))

		return items
