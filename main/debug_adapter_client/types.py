from debug.core.typecheck import NamedTuple, Optional as Option

if False: from .client import DebugAdapterClient
		
class StackFramePresentation:
	normal = 1
	label = 2
	subtle = 3

class StackFrame:
	def __init__(self, id: int, file: str, name: str, line: int, internal: bool, presentation: int) -> None:
		self.id = id
		self.name = name
		self.file = file
		self.line = line
		self.internal = internal
		self.presentation = presentation

class Variable:
	def __init__(self, adapter: 'DebugAdapterClient', name: str, value: str, reference: int) -> None:
		self.adapter = adapter
		self.name = name
		self.value = value
		self.reference = reference

class Thread:
	def __init__(self, id: int, name: str) -> None:
		self.id = id
		self.name = name
		self.stopped = False
		self.selected = False
		self.expanded = False