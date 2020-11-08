from ...typecheck import *
from ...import core
from ...import ui

from .. import dap

from . import css


class SourcesView(ui.div):
	def __init__(self, sessions: dap.Sessions, on_click: Callable[[dap.SourceLocation], None]):
		super().__init__()
		self.sessions = sessions
		self.on_click = on_click

	def added(self, layout: ui.Layout):
		self.on_updated_sources = self.sessions.on_updated_sources.add(self.updated)
		self.on_removed_session = self.sessions.on_removed_session.add(self.updated)

	def updated(self, session: dap.Session):
		self.dirty()

	def removed(self):
		self.on_updated_sources.dispose()
		self.on_removed_session.dispose()

	def render(self) -> ui.div.Children:
		items = []
		for session in self.sessions:
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

	def render(self) -> ui.div.Children:
		items = [
			ui.div(height=css.row_height)[
				ui.align()[
					ui.click(lambda: self.on_click(dap.SourceLocation(self.source, None, None)))[
						ui.text(self.source.path or self.source.name or "<no source name>", css=css.label_secondary)
					]
				]
			]
		]
		for sub_source in self.source.sources:
			items.append(SourceView(sub_source, self.on_click))

		return items
