
from sublime_db.core.typecheck import (List, Callable, Optional)
from sublime_db import ui
from sublime_db import core

from sublime_db.main.debugger import (
	Thread,
	DebugAdapterClient
)

from .thread_component import ThreadComponent

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
