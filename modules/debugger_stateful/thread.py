from sublime_debug.modules.core.typecheck import (List, Callable, Optional, TYPE_CHECKING)
from sublime_debug.modules import core

from sublime_debug.modules.debugger_stateful.debugger import (
	Thread,
	StackFrame,
	DebugAdapterClient,
)

if TYPE_CHECKING:
	from sublime_debug.modules.debugger_stateful.debugger import DebuggerStateful

class ThreadStateful:
	def __init__(self, debugger: 'DebuggerStateful', id: int, name: Optional[str], stopped: bool):
		self.debugger = debugger
		self.fetched = False
		self._id = id
		self._name = name
		self._stopped = stopped
		self._expanded = False
		self._frames = []
		self.on_dirty = None

	@property
	def id(self):
		return self._id

	@property
	def name(self)->str:
		return self._name or "unknown"

	def update_name(self, name: str):
		if self._name == None or self._name != name:
			self._name = name
			self.dirty()

	def expand(self):
		self._expanded = True
		self.fetch_if_needed()
		self.dirty()

	def collapse(self):
		self._expanded = False
		self.dirty()

	def dirty(self):
		if self.on_dirty:
			self.on_dirty()

	@property
	def expanded(self):
		return self._expanded

	@property
	def stopped(self):
		return self._stopped

	@property
	def frames(self)->List[StackFrame]:
		if self.expanded and self.stopped and self.fetched:
			return self._frames
		return []

	def fetch_if_needed(self):
		if not self._stopped or self.fetched:
			return

		self.fetched = True
		def response(frames: List[StackFrame]):
			self._frames = frames
			self.debugger.update_selection_if_needed()
			self.dirty()

		core.run(self.debugger.adapter.GetStackTrace(self), response)
		self.dirty()

	def on_continued(self):
		self.fetched = False
		self._stopped = False
		self.dirty()

	def on_stopped(self, stopped_text: str):
		self._stopped = True
		self.fetched = False
		self.stopped_text = stopped_text
		self.fetch_if_needed()
		self.dirty()
