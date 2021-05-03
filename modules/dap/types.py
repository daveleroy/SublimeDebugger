from __future__ import annotations
from ..typecheck import *
from ..import core

from dataclasses import dataclass

T = TypeVar('T')
V = TypeVar('V')

Json = Dict[str, Any]

def array_from_json(from_json: Callable[[Json], T], json_array: list[Json]) -> list[T]:
	items: list[T] = []
	for json in json_array:
		items.append(from_json(json))
	return items

def json_from_array(into_json: Callable[[T], Json], array: list[T]) -> list[Any]:
	json: list[Any] = []
	for item in array:
		json.append(into_json(item))
	return json

def _remove_empty(dict: Json):
	rm: list[str] = []
	for key, value in dict.items():
		if value is None:
			rm.append(key)

	for key in rm:
		del dict[key]

	return dict

class _DefaultDict(Dict[T, V]):
	def __missing__(self, key: str):
		return key.join("{}")

class Error(core.Error):
	def __init__(self, showUser: bool, format: str):
		super().__init__(format)
		self.showUser = showUser

	@staticmethod
	def from_json(json: Json):
		# why on earth does the optional error details have variables that need to be formatted in it????????
		format = json.get('format', 'No error reason given')
		variables = _DefaultDict(**json.get('variables', {}))
		error_message = format.format_map(variables)
		return Error(json.get('showUser', True), error_message)


@dataclass
class Thread:
	id: int
	name: str

	@staticmethod
	def from_json(json: Json):
		return Thread(
			id=json['id'],
			name=json['name'],
		)

@dataclass
class StackFrame:
	id: int
	file: str
	name: str
	line: int
	column: int
	presentation: str
	source: Source|None

	normal: ClassVar[str] = 'normal'
	label: ClassVar[str] = 'label'
	subtle: ClassVar[str] = 'subtle'
	deemphasize: ClassVar[str] = 'deemphasize'

	@staticmethod
	def from_json(frame: Json):
		file = '??'
		source_json = frame.get('source')
		source = None #type: Source|None
		if source_json:
			source = Source.from_json(source_json)
			file = source.name or "??"

		return StackFrame(
			frame['id'],
			file,
			frame['name'],
			frame.get('line', 0),
			frame.get('column', 0),
			frame.get('presentationHint', 'normal'),
			source
		)

@dataclass
class Scope:
	name: str
	variablesReference: int
	expensive: bool

	@staticmethod
	def from_json(json: Json):
		return Scope(
			name=json['name'],
			variablesReference=json['variablesReference'],
			expensive=json.get('expensive', False) # some adapters treat this as optional
		)

@dataclass
class Variable:
	name: str
	value: str
	variablesReference: int
	containerVariablesReference: int = 0
	evaluateName: str|None = None

	@staticmethod
	def from_json(containerVariablesReference: int, json: Json):
		return Variable(
			name=json['name'],
			value=json['value'],
			variablesReference=json.get('variablesReference', 0),
			containerVariablesReference=containerVariablesReference,
			evaluateName=json.get('evaluateName'),
		)

@dataclass
class EvaluateResponse:
	result: str
	variablesReference: int

@dataclass
class CompletionItem:
	label: str
	text: str | None
	sortText: str | None
	type: str | None #'removed' 'method' 'function' 'constructor' 'field' 'variable' 'class' 'interface' 'module' 'property' 'unit' 'value' 'enum' 'keyword' 'snippet' 'text' 'color' 'file' 'reference' 'customcolor'


	@staticmethod
	def from_json(json: Json):
		return CompletionItem(
			json['label'],
			json.get('text', None),
			json.get('sortText', None),
			json.get('type', None),
		)

@dataclass
class Source:
	name: str|None
	path: str|None
	sourceReference: int = 0
	presentationHint: str|None = 'normal'
	origin: str|None = None
	# sources: list['Source'] = []

	normal: ClassVar[str] = 'normal'
	emphasize: ClassVar[str] = 'emphasize'
	deemphasize: ClassVar[str] = 'deemphasize'

	@property
	def id(self) -> str:
		return f'{self.name}~{self.path}~{self.sourceReference}'

	@staticmethod
	def from_json(json: Json):
		return Source(
			json.get('name'),
			json.get('path'),
			json.get('sourceReference', 0),
			json.get('presentationHint'),
			json.get('origin'),
			# array_from_json(Source.from_json, json.get('sources', []))
		)

@dataclass
class ExceptionBreakpointsFilter:
	id: str
	label: str
	description: str|None
	default: bool
	supportsCondition: bool
	conditionDescription: str|None

	@staticmethod
	def from_json(json: Json):
		return ExceptionBreakpointsFilter(
			json['filter'],
			json['label'],
			json.get('description', None),
			json.get('default', False),
			json.get('supportsCondition', False),
			json.get('conditionDescription', None),
		)

	def into_json(self) -> Json:
		return {
			'filter': self.id,
			'label': self.label,
			'default': self.default,
		}

@dataclass
class Capabilities:
	supportsConfigurationDoneRequest: bool
	supportsFunctionBreakpoints: bool
	supportsConditionalBreakpoints: bool
	supportsHitConditionalBreakpoints: bool
	supportsEvaluateForHovers: bool
	exceptionBreakpointFilters: list[ExceptionBreakpointsFilter]
	supportsStepBack: bool
	supportsSetVariable: bool
	supportsRestartFrame: bool
	supportsGotoTargetsRequest: bool
	supportsStepInTargetsRequest: bool
	supportsCompletionsRequest: bool
	supportsModulesRequest: bool
	supportsRestartRequest: bool
	supportsExceptionOptions: bool
	supportsValueFormattingOptions: bool
	supportsExceptionInfoRequest: bool
	supportsTerminateDebuggee: bool
	supportsDelayedStackTraceLoading: bool
	supportsLoadedSourcesRequest: bool
	supportsLogPoints: bool
	supportsTerminateThreadsRequest: bool
	supportsSetExpression: bool
	supportsTerminateRequest: bool
	supportsDataBreakpoints: bool
	supportsReadMemoryRequest: bool
	supportsDisassembleRequest: bool
	supportsCancelRequest: bool
	supportsBreakpointLocationsRequest: bool
	supportsClipboardContext: bool
	supportsSteppingGranularity: bool
	supportsInstructionBreakpoints: bool
	supportsExceptionFilterOptions: bool

	@staticmethod
	def from_json(json: Json):
		return Capabilities(
			supportsConfigurationDoneRequest=json.get('supportsConfigurationDoneRequest', False),
			supportsFunctionBreakpoints=json.get('supportsFunctionBreakpoints', False),
			supportsConditionalBreakpoints=json.get('supportsConditionalBreakpoints', False),
			supportsHitConditionalBreakpoints=json.get('supportsHitConditionalBreakpoints', False),
			supportsEvaluateForHovers=json.get('supportsEvaluateForHovers', False),
			exceptionBreakpointFilters=array_from_json(ExceptionBreakpointsFilter.from_json, json.get('exceptionBreakpointFilters', [])),
			supportsStepBack=json.get('supportsStepBack', False),
			supportsSetVariable=json.get('supportsSetVariable', False),
			supportsRestartFrame=json.get('supportsRestartFrame', False),
			supportsGotoTargetsRequest=json.get('supportsGotoTargetsRequest', False),
			supportsStepInTargetsRequest=json.get('supportsStepInTargetsRequest', False),
			supportsCompletionsRequest=json.get('supportsCompletionsRequest', False),
			supportsModulesRequest=json.get('supportsModulesRequest', False),
			# additionalModuleColumns=json['additionalModuleColumns']?:ColumnDescriptor[];
			# supportedChecksumAlgorithms=json['supportedChecksumAlgorithms']?:ChecksumAlgorithm[];
			supportsRestartRequest=json.get('supportsRestartRequest', False),
			supportsExceptionOptions=json.get('supportsExceptionOptions', False),
			supportsValueFormattingOptions=json.get('supportsValueFormattingOptions', False),
			supportsExceptionInfoRequest=json.get('supportsExceptionInfoRequest', False),
			supportsTerminateDebuggee=json.get('supportsTerminateDebuggee', False),
			supportsDelayedStackTraceLoading=json.get('supportsDelayedStackTraceLoading', False),
			supportsLoadedSourcesRequest=json.get('supportsLoadedSourcesRequest', False),
			supportsLogPoints=json.get('supportsLogPoints', False),
			supportsTerminateThreadsRequest=json.get('supportsTerminateThreadsRequest', False),
			supportsSetExpression=json.get('supportsSetExpression', False),
			supportsTerminateRequest= json.get('supportsTerminateRequest', False),
			supportsDataBreakpoints= json.get('supportsDataBreakpoints', False),
			supportsReadMemoryRequest=json.get('supportsReadMemoryRequest', False),
			supportsDisassembleRequest=json.get('supportsDisassembleRequest', False),
			supportsCancelRequest=json.get('supportsCancelRequest', False),
			supportsBreakpointLocationsRequest=json.get('supportsBreakpointLocationsRequest', False),
			supportsClipboardContext=json.get('supportsClipboardContext', False),
			supportsSteppingGranularity=json.get('supportsSteppingGranularity', False),
			supportsInstructionBreakpoints=json.get('supportsInstructionBreakpoints', False),
			supportsExceptionFilterOptions=json.get('supportsExceptionFilterOptions', False),
		)

@dataclass
class StoppedEvent:
	threadId: int
	allThreadsStopped: bool
	text: str

	@staticmethod
	def from_json(json: Json):
		# stopped events are required to have a reason but some adapters treat it as optional...
		description = json.get('description')
		text = json.get('text')
		reason = json.get('reason')

		if description and text:
			stopped_text = "Stopped: {}: {}".format(description, text)
		elif text or description or reason:
			stopped_text = "Stopped: {}".format(text or description or reason)
		else:
			stopped_text = "Stopped"

		return StoppedEvent(
			threadId=json.get('threadId', None),
			allThreadsStopped=json.get('allThreadsStopped', False),
			text=stopped_text,
		)

@dataclass
class ThreadEvent:
	threadId: int
	reason: str

	@staticmethod
	def from_json(json: Json):
		return ThreadEvent(
			threadId=json['threadId'],
			reason=json['reason'],
		)

@dataclass
class TerminatedEvent:
	restart: Any|None

	@staticmethod
	def from_json(json: Json):
		return TerminatedEvent(json.get('restart'))

@dataclass
class ContinueResponse:
	allThreadsContinued: bool

	@staticmethod
	def from_json(json: Json):
		return ContinueResponse(json.get('allThreadsContinued', True))


@dataclass
class ContinuedEvent:
	threadId: int
	allThreadsContinued: bool

	@staticmethod
	def from_json(json: Json):
		return ContinuedEvent(
			threadId=json['threadId'],
			allThreadsContinued=json.get('allThreadsContinued', None),
		)

@dataclass
class OutputEvent:
	category: str
	text: str
	variablesReference: int
	source: Source|None = None
	line: int|None = None

	@staticmethod
	def from_json(json: Json):
		category = json.get('category', 'console')
		source = json.get('source')
		if source:
			source = Source.from_json(source)

		return OutputEvent(
			category,
			json['output'],
			json.get('variablesReference', 0),
			source,
			json.get('line'))


@dataclass
class RunInTerminalRequest:
	kind: str
	title: str
	cwd: str
	args: list[str]
	env: dict[str, str|None]

	@staticmethod
	def from_json(json: Json):
		return RunInTerminalRequest(
			json.get('kind', 'integrated'),
			json.get('title', 'No Title'),
			json['cwd'],
			json['args'],
			json.get('env', {})
		)

@dataclass
class RunInTerminalResponse:
	processId: int|None
	shellProcessId: int|None

	def into_json(self) -> Json:
		return {
			'processId': self.processId,
			'shellProcessId': self.shellProcessId,
		}


@dataclass
class DataBreakpoint:
	id: str
	accessType: str|None
	condition: str|None
	hitCondition: str|None

	read: ClassVar[str] = 'read'
	write: ClassVar[str] = 'write'
	readWrite: ClassVar[str] = 'readWrite'

	def into_json(self) -> Json:
		return {
			'processId': self.id,
			'accessType': self.accessType,
			'condition': self.condition,
			'hitCondition': self.hitCondition,
		}
	@staticmethod
	def from_json(json: Json):
		return DataBreakpoint(
			json['dataId'],
			json['accessType'],
			json['condition'],
			json['hitCondition'],
		)

@dataclass
class DataBreakpointInfoResponse:
	id: str|None
	description: str
	accessTypes: list[str]
	canPersist: bool

	@staticmethod
	def from_json(json: Json):
		return DataBreakpointInfoResponse(
			json.get('dataId'),
			json.get('description', 'no data description'),
			json.get('accessTypes', []),
			json.get('canPersist', False),
		)

	def into_json(self) -> Json:
		return {
			'dataId': self.id,
			'description': self.description,
			'accessTypes': self.accessTypes,
			'canPersist': self.canPersist,
		}

@dataclass
class FunctionBreakpoint:
	name: str
	condition: str|None
	hitCondition: str|None

	@staticmethod
	def from_json(json: Json):
		return FunctionBreakpoint(
			json['name'],
			json.get('condition'),
			json.get('hitCondition'),
		)

	def into_json(self) -> Json:
		return {
			'name': self.name,
			'condition': self.condition,
			'hitCondition': self.hitCondition,
		}

@dataclass
class SourceBreakpoint:
	line: int
	column: int|None
	condition: str|None
	hitCondition: str|None
	logMessage: str|None

	@staticmethod
	def from_json(json: Json):
		return SourceBreakpoint(
			json['line'],
			json.get('column'),
			json.get('condition'),
			json.get('hitCondition'),
			json.get('logMessage'),
		)

	def into_json(self) -> Json:
		# chrome debugger hates null column
		return _remove_empty({
			'line': self.line,
			'column': self.column,
			'condition': self.condition,
			'hitCondition': self.hitCondition,
			'logMessage': self.logMessage,
		})

@dataclass
class BreakpointResult:
	verified: bool
	line: int|None
	column: int|None
	message: str|None
	id: int|None

	failed: ClassVar[BreakpointResult] = None #type: ignore

	@staticmethod
	def from_json(json: Json):
		return BreakpointResult(
			json['verified'],
			json.get('line'),
			json.get('column'),
			json.get('message'),
			json.get('id')
		)

BreakpointResult.failed = BreakpointResult(False, None, None, None, None)

@dataclass
class BreakpointEvent:
	reason: str
	result: BreakpointResult

	@staticmethod
	def from_json(json: Json):
		return BreakpointEvent (
			json['reason'],
			BreakpointResult.from_json(json['breakpoint']),
		)

@dataclass
class Module:
	id: Union[int, str]
	name: str
	path: str|None
	isOptimized: bool|None
	isUserCode: bool|None
	version: str|None
	symbolStatus: str|None
	symbolFilePath: str|None
	dateTimeStamp: str|None
	addressRange: str|None

	@staticmethod
	def from_json(json: Json):
		return Module(
			id = json['id'],
			name = json['name'],
			path = json.get('path'),
			isOptimized = json.get('isOptimized'),
			isUserCode = json.get('isUserCode'),
			version = json.get('version'),
			symbolStatus = json.get('symbolStatus'),
			symbolFilePath = json.get('symbolFilePath'),
			dateTimeStamp = json.get('dateTimeStamp'),
			addressRange = json.get('addressRange'),
		)

@dataclass
class ModuleEvent:
	reason: str
	module: Module

	new: ClassVar[str] = 'new'
	changed: ClassVar[str] = 'changed'
	removed: ClassVar[str] = 'removed'

	@staticmethod
	def from_json(json: Json):
		return ModuleEvent(
			json['reason'],
			Module.from_json(json['module'])
		)

@dataclass
class LoadedSourceEvent:
	reason: str
	source: Source

	new: ClassVar[str] = 'new'
	changed: ClassVar[str] = 'changed'
	removed: ClassVar[str] = 'removed'

	@staticmethod
	def from_json(json: Json):
		return LoadedSourceEvent(
			json['reason'],
			Source.from_json(json['source'])
		)
