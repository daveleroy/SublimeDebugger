from sublime_db.core.typecheck import (List, Callable, Optional)
from sublime_db import ui
from sublime_db import core

from sublime_db.main.debugger import (
	Scope,
	Thread,
	DebugAdapterClient
)

from .variable_component import ScopeComponent
from .thread_component import ThreadComponent

class VariablesPanel (ui.Component):
	def __init__(self) -> None:
		super().__init__()
		self.scopes = [] #type: List[Scope]

	def clear(self) -> None:
		self.scopes = []
		self.dirty()

	def set_scopes(self, scopes: List[Scope]) -> None:
		self.scopes = scopes
		self.dirty()

	def render(self) -> ui.components:
		items = [
			ui.Segment(items = [ui.Label('Variables')])
		] #type: List[ui.Component]

		scopes_items = [] #type: List[ui.Component]

		# expand the first scope only
		first = True
		for v in self.scopes:
			scopes_item = ScopeComponent(v)
			if first:
				first = False
				scopes_item.scope.toggle_expand()
			scopes_items.append(scopes_item)
		
		items.append(ui.Table(items = scopes_items))
		
		return [
			ui.HorizontalSpacer(250),
			ui.Panel(items = items)
		]

class CallStackPanel (ui.Component):
	def __init__(self) -> None:
		super().__init__()
		self.threads = [] #type: List[Thread]
		self.selected = 0 #type: int
		self.error = False #type: bool
		self.thread_components = [] #type: List[ThreadComponent]

	def clear(self) -> None:
		self.setThreads(None, [], False)
		
	def dirty_threads(self) -> None:
		for thread_component in self.thread_components:
			thread_component.dirty()

	def setThreads(self, debugger: Optional[DebugAdapterClient], threads: List[Thread], error: bool) -> None:
		self.threads = threads
		self.debugger = debugger
		self.error = error
		self.dirty()
		
	def render(self) -> ui.components:			
		self.thread_components = []
		for index, thread in enumerate(self.threads):
			assert self.debugger
			item = ThreadComponent(self.debugger, thread)
			self.thread_components.append(item)
		return [
			ui.HorizontalSpacer(250),
			ui.Panel(items = [
				ui.Segment(items = [
					ui.Label('Call Stack')
				]),
				# FIXME?? Table should not take List
				ui.Table(items = self.thread_components) #type: ignore 
			])
		]
