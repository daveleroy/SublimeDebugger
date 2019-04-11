from sublime_db.core.typecheck import TYPE_CHECKING, Optional, List, Callable, TypeVar

if TYPE_CHECKING:
	from .client import DebugAdapterClient


T = TypeVar('T')


def array_from_json(from_json: Callable[[], T], json_array: list) -> T:
	items = []
	for json in json_array:
		items.append(from_json(json))
	return items


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

	def __init__(self, name: Optional[str], path: Optional[str], sourceReference: int, presentationHint: int, origin: Optional[str], sources: List['Source']) -> None:
		self.name = name or path
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

		sources = array_from_json(Source.from_json, json.get('sources', []))

		return Source(
			json.get('name'),
			json.get('path'),
			json.get('sourceReference', 0),
			hint,
			json.get('origin'),
			sources
		)


class ExceptionBreakpointsFilter:
	def __init__(self, id: str, label: str, default: bool) -> None:
		self.id = id
		self.label = label
		self.default = default

	@staticmethod
	def from_json(json: dict) -> 'Filter':
		return ExceptionBreakpointsFilter(
			json['filter'],
			json['label'],
			json.get('default', False),
		)


class Capabilities:
	def __init__(self, json: dict):
		self.supportsConfigurationDoneRequest = json.get('supportsConfigurationDoneRequest', False)
		self.supportsFunctionBreakpoints = json.get('supportsFunctionBreakpoints', False)
		self.supportsConditionalBreakpoints = json.get('supportsConditionalBreakpoints', False)
		self.supportsHitConditionalBreakpoints = json.get('supportsHitConditionalBreakpoints', False)
		self.supportsEvaluateForHovers = json.get('supportsEvaluateForHovers', False)
		self.exceptionBreakpointFilters = array_from_json(ExceptionBreakpointsFilter.from_json, json.get('exceptionBreakpointFilters', []))
		self.supportsStepBack = json.get('supportsStepBack', False)
		self.supportsSetVariable = json.get('supportsSetVariable', False)
		self.supportsRestartFrame = json.get('supportsRestartFrame', False)
		self.supportsGotoTargetsRequest = json.get('supportsGotoTargetsRequest', False)
		self.supportsStepInTargetsRequest = json.get('supportsStepInTargetsRequest', False)
		self.supportsCompletionsRequest = json.get('supportsCompletionsRequest', False)
		self.supportsModulesRequest = json.get('supportsModulesRequest', False)
		# additionalModuleColumns = json['additionalModuleColumns']?: ColumnDescriptor[];
		# supportedChecksumAlgorithms = json['supportedChecksumAlgorithms']?: ChecksumAlgorithm[];
		self.supportsRestartRequest = json.get('supportsRestartRequest', False)
		self.supportsExceptionOptions = json.get('supportsExceptionOptions', False)
		self.supportsValueFormattingOptions = json.get('supportsValueFormattingOptions', False)
		self.supportsExceptionInfoRequest = json.get('supportsExceptionInfoRequest', False)
		self.supportTerminateDebuggee = json.get('supportTerminateDebuggee', False)
		self.supportsDelayedStackTraceLoading = json.get('supportsDelayedStackTraceLoading', False)
		self.supportsLoadedSourcesRequest = json.get('supportsLoadedSourcesRequest', False)
		self.supportsLogPoints = json.get('supportsLogPoints', False)
		self.supportsTerminateThreadsRequest = json.get('supportsTerminateThreadsRequest', False)
		self.supportsSetExpression = json.get('supportsSetExpression', False)
		self.supportsTerminateRequest = json.get('supportsTerminateRequest', False)

	@staticmethod
	def from_json(json: dict) -> 'Capabilities':
		return Capabilities(json)
