from ..typecheck import *
from ..import dap
from ..import core
from ..import ui

class Sources:
	def __init__(self):
		self.sources = [] #type: List[dap.Source]
		self.on_updated = core.Event() #type: core.Event[None]

	def on_loaded_source_event(self, event: dap.LoadedSourceEvent) -> None:
		if event.reason == dap.LoadedSourceEvent.new:
			self.sources.append(event.source)
			self.on_updated()
			return
		if event.reason == dap.LoadedSourceEvent.new:
			# FIXME: NOT IMPLEMENTED
			return
		if event.reason == dap.LoadedSourceEvent.new:
			# FIXME: NOT IMPLEMENTED
			return

	def clear_session_date(self) -> None:
		self.sources.clear()
		self.on_updated()

class SourcesView(ui.Block):
	def __init__(self, sources: Sources):
		super().__init__()
		self.sources = sources

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.sources.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def render(self) -> ui.Panel.Children:
		items = []
		for module in self.sources.sources:
			items.append(
				ui.block(
					ui.Label(module.name)
				)
			)
		return [
			ui.Table(items=items)
		]
