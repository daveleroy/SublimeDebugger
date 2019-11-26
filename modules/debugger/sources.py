from ..typecheck import *
from ..import dap
from ..import core
from ..import ui
from ..components import css

class Sources:
	def __init__(self):
		self.sources = [] #type: List[dap.Source]
		self.on_updated = core.Event() #type: core.Event[None]

	def on_loaded_source_event(self, event: dap.LoadedSourceEvent) -> None:
		if event.reason == dap.LoadedSourceEvent.new:
			self.sources.append(event.source)
			self.on_updated()
			return
		if event.reason == dap.LoadedSourceEvent.removed:
			# FIXME: NOT IMPLEMENTED
			return
		if event.reason == dap.LoadedSourceEvent.changed:
			# FIXME: NOT IMPLEMENTED
			return

	def clear_session_date(self) -> None:
		self.sources.clear()
		self.on_updated()

class SourcesView(ui.div):
	def __init__(self, sources: Sources, on_click: Callable[[dap.Source], None]):
		super().__init__()
		self.sources = sources
		self.on_click = on_click

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.sources.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def render(self) -> ui.div.Children:
		items = []
		for source in self.sources.sources:
			items.append(SourceView(source, self.on_click))

		return [
			ui.div()[items]
		]

class SourceView(ui.div):
	def __init__(self, source: dap.Source, on_click: Callable[[dap.Source], None]):
		super().__init__()
		self.source = source
		self.on_click = on_click

	def render(self) -> ui.div.Children:
		items = [
			ui.div(height=3)[
				ui.click(lambda: self.on_click(self.source))[
					ui.text(self.source.path or self.source.name or "<no source name>", css=css.label_secondary)
				]
			]
		]
		for sub_source in self.source.sources:
			items.append(SourceView(sub_source, self.on_click))

		return items
