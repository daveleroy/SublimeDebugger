from sublime_db.core.typecheck import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
	from .client import DebugAdapterClient


class Error(Exception):
	def __init__(self, showUser: bool, format: str):
		super().__init__(format)
		self.showUser = showUser

	@staticmethod
	def from_json(json: dict) -> 'Error':
		return Error(json.get('showUser', True), json.get('format', 'No error reason given'))


class Thread:
	def __init__(self, client: 'DebugAdapterClient', id: int, name: str) -> None:
		self.client = client
		self.id = id
		self.name = name
		self.stopped = False
		self.stopped_text = ""
		self.expanded = False


class StackFrame:
	normal = 1
	label = 2
	subtle = 3

	def __init__(self, thread: Thread, id: int, file: str, name: str, line: int, presentation: int, source: Optional['Source']) -> None:
		self.thread = thread
		self.id = id
		self.name = name
		self.file = file
		self.line = line
		self.presentation = presentation
		self.source = source

	@staticmethod
	def from_json(thread: Thread, frame: dict) -> 'StackFrame':
		file = '??'
		source_json = frame.get('source')
		source = None #type: Optional[Source]
		if source_json:
			source = Source.from_json(source_json)
			file = source.name

		hint = frame.get('presentationHint', 'normal')

		if hint == 'label':
			presentation = StackFrame.label
		elif hint == 'subtle':
			presentation = StackFrame.subtle
		else:
			presentation = StackFrame.normal

		return StackFrame(
			thread,
			frame['id'],
			file,
			frame['name'],
			frame.get('line', 0),
			presentation,
			source
		)


class Scope:
	def __init__(self, client: 'DebugAdapterClient', name: str, variablesReference: int, expensive: bool) -> None:
		self.client = client
		self.name = name
		self.variablesReference = variablesReference
		self.expensive = expensive

	@staticmethod
	def from_json(client: 'DebugAdapterClient', json: dict) -> 'Scope':
		return Scope(
			client,
			json['name'],
			json['variablesReference'],
			json.get('expensive', False) # some adapters treat this as optional
		)


class Variable:
	def __init__(self, client: 'DebugAdapterClient', name: str, value: str, variablesReference: int, containerVariablesReference: int = 0) -> None:
		self.client = client
		self.name = name
		self.value = value
		self.containerVariablesReference = 0
		self.variablesReference = variablesReference

	@staticmethod
	def from_json(client: 'DebugAdapterClient', json: dict) -> 'Variable':
		return Variable(
			client,
			json['name'],
			json['value'],
			json.get('variablesReference', 0)
		)


class EvaluateResponse:
	def __init__(self, result: str, variablesReference: int) -> None:
		self.result = result
		self.variablesReference = variablesReference


class CompletionItem:
	def __init__(self, label: str, text: str) -> None:
		self.label = label
		self.text = text

	@staticmethod
	def from_json(json: dict) -> 'CompletionItem':
		return CompletionItem(
			json['label'],
			json.get('text', None),
		)


class Source:

	normal = 1
	emphasize = 2
	deemphasize = 3

	def __init__(self, name: str, path: Optional[str], sourceReference: int, presentationHint: int, origin: Optional[str], sources: List['Source']) -> None:
		self.name = name
		self.path = path
		self.sourceReference = sourceReference
		self.presentationHint = presentationHint
		self.origin = origin
		self.sources = sources

	@staticmethod
	def from_json(json: dict) -> 'Source':
		hint = Source.normal
		json_hint = json.get('presentationHint')
		if json_hint:
			if json_hint == 'emphasize':
				hint = Source.emphasize
			elif json_hint == 'deemphasize':
				hint = Source.deemphasize

		sources = []
		for source_json in json.get('sources', []):
			sources.append(Source.from_json(source_json))

		return Source(
			json.get('name', '??'),
			json.get('path'),
			json.get('sourceReference', 0),
			hint,
			json.get('origin'),
			sources
		)
