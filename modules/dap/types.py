from ..typecheck import *
if TYPE_CHECKING:
	from .client import Client


__T = TypeVar('__T')


def array_from_json(from_json: Callable[[dict], __T], json_array: list) -> List[__T]:
	items = []
	for json in json_array:
		items.append(from_json(json))
	return items

def json_from_array(into_json: Callable[[__T], dict], array: List[__T]) -> list:
	json = []
	for item in array:
		json.append(into_json(item))
	return json

class Error(Exception):
	def __init__(self, showUser: bool, format: str):
		super().__init__(format)
		self.showUser = showUser

	@staticmethod
	def from_json(json: dict) -> 'Error':
		# why on earth does the optional error details have variables that need to be formatted in it????????
		format = json.get('format', 'No error reason given')
		variables = json.get('variables', {})
		error_message = format.format(**variables)
		return Error(json.get('showUser', True), error_message)


class Thread:
	def __init__(self, client: 'Client', id: int, name: str) -> None:
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
			file = source.name or "??"

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
	def __init__(self, client: 'Client', name: str, variablesReference: int, expensive: bool) -> None:
		self.client = client
		self.name = name
		self.variablesReference = variablesReference
		self.expensive = expensive

	@staticmethod
	def from_json(client: 'Client', json: dict) -> 'Scope':
		return Scope(
			client,
			json['name'],
			json['variablesReference'],
			json.get('expensive', False) # some adapters treat this as optional
		)


class Variable:
	def __init__(self, client: 'Client', name: str, value: str, variablesReference: int, containerVariablesReference: int = 0, evaluateName: Optional[str] = None) -> None:
		self.client = client
		self.name = name
		self.value = value
		self.containerVariablesReference = 0
		self.variablesReference = variablesReference
		self.evaluateName = evaluateName

	@staticmethod
	def from_json(client: 'Client', json: dict) -> 'Variable':
		return Variable(
			client,
			json['name'],
			json['value'],
			json.get('variablesReference', 0),
			evaluateName=json.get('evaluateName'),
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
	def from_json(json: dict) -> 'ExceptionBreakpointsFilter':
		return ExceptionBreakpointsFilter(
			json['filter'],
			json['label'],
			json.get('default', False),
		)

	def into_json(self) -> dict:
		return {
			'filter': self.id,
			'label': self.label,
			'default': self.default,
		}

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
		self.supportsDataBreakpoints = json.get('supportsDataBreakpoints', False)

	@staticmethod
	def from_json(json: dict) -> 'Capabilities':
		return Capabilities(json)


class StoppedEvent:
	def __init__(self, threadId: int, allThreadsStopped: bool, text: str) -> None:
		self.threadId = threadId
		self.allThreadsStopped = allThreadsStopped
		self.text = text


class ThreadEvent:
	def __init__(self, threadId: int, reason: str) -> None:
		self.threadId = threadId
		self.reason = reason

	@staticmethod
	def from_json(json) -> 'ThreadEvent':
		return ThreadEvent(json['threadId'], json['reason'])


class TerminatedEvent:
	def __init__(self, restart: Optional[Any]) -> None:
		self.restart = restart

	@staticmethod
	def from_json(json) -> 'TerminatedEvent':
		return TerminatedEvent(json.get('restart'))


class ContinuedEvent:
	def __init__(self, threadId: int, allThreadsContinued: bool) -> None:
		self.threadId = threadId
		self.allThreadsContinued = allThreadsContinued


class OutputEvent:
	def __init__(self, category: str, text: str, variablesReference: int, source: Optional[Source] = None, line: Optional[int] = None) -> None:
		self.category = category
		self.text = text
		self.variablesReference = variablesReference
		self.source = source
		self.line = line

	@staticmethod
	def from_json(json) -> 'OutputEvent':
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


class RunInTerminalRequest:
	def __init__(self, kind: str, title: str, cwd: str, args: List[str], env: Dict[str, Optional[str]]) -> None:
		self.kind = kind
		self.title = title
		self.cwd = cwd
		self.args = args
		self.env = env

	@staticmethod
	def from_json(json) -> 'RunInTerminalRequest':
		return RunInTerminalRequest(
			json.get('kind', 'integrated'), 
			json.get('title', 'No Title'), 
			json['cwd'],
			json['args'],
			json.get('env', {})
		)


class DataBreakpoint:
	read = 'read'
	write = 'write'
	readWrite ='readWrite'

	def __init__(self, id: str, accessType: Optional[str], condition: Optional[str], hitCondition: Optional[str]) -> None:
		self.id = id
		self.accessType = accessType
		self.condition = condition
		self.hitCondition = hitCondition
	def into_json(self) -> dict:
		return {
			'dataId': self.id,
			'accessType': self.accessType,
			'condition': self.condition,
			'hitCondition': self.hitCondition,
		}
	@staticmethod
	def from_json(json: dict) -> 'DataBreakpoint':
		return DataBreakpoint(
			json['dataId'],
			json['accessType'],
			json['condition'],
			json['hitCondition'],
		)

class DataBreakpointInfoResponse:
	def __init__(self, id: Optional[str], description: str, accessTypes: List[str], canPersist: bool) -> None:
		self.id = id
		self.description = description
		self.accessTypes = accessTypes
		self.canPersist = canPersist

	@staticmethod
	def from_json(json) -> 'DataBreakpointInfoResponse':
		return DataBreakpointInfoResponse(
			json.get('dataId'), 
			json.get('description', 'no data description'), 
			json.get('accessTypes', []),
			json.get('canPersist', False),
		)

	def into_json(self) -> dict:
		return {
			'dataId': self.id,
			'description': self.description,
			'accessTypes': self.accessTypes,
			'canPersist': self.canPersist,
		}

class FunctionBreakpoint:
	def __init__(self, name: str, condition: Optional[str], hitCondition: Optional[str]) -> None:
		self.name = name
		self.condition = condition
		self.hitCondition = hitCondition

	@staticmethod
	def from_json(json) -> 'FunctionBreakpoint':
		return FunctionBreakpoint(
			json.get('name'), 
			json.get('condition'), 
			json.get('hitCondition'),
		)

	def into_json(self) -> dict:
		return {
			'name': self.name,
			'condition': self.condition,
			'hitCondition': self.hitCondition,
		}

class SourceBreakpoint:
	def __init__(self, line: int, column: Optional[int], condition: Optional[str], hitCondition: Optional[str], logMessage: Optional[str]) -> None:
		self.line = line
		self.column = column
		self.condition = condition
		self.hitCondition = hitCondition
		self.logMessage = logMessage

	@staticmethod
	def from_json(json) -> 'SourceBreakpoint':
		return SourceBreakpoint(
			json.get('line'), 
			json.get('column'), 
			json.get('condition'),
			json.get('hitCondition'),
			json.get('logMessage'),
		)

	def into_json(self) -> dict:
		# chrome debugger hates null column
		return _remove_empty({
			'line': self.line,
			'column': self.column,
			'condition': self.condition,
			'hitCondition': self.hitCondition,
			'logMessage': self.logMessage,
		})

def _remove_empty(dict: dict):
	rm = []
	for key, value in dict.items():
		if value is None:
			rm.append(key)
	
	for key in rm:
		del dict[key]

	return dict

class BreakpointResult:
	
	def __init__(self, verified: bool, line: Optional[int], column: Optional[int], message: Optional[str], id = None) -> None:
		self.verified = verified
		self.line = line
		self.column = column
		self.message = message
		self.id = id

	@staticmethod
	def from_json(json: dict) -> 'BreakpointResult':
		return BreakpointResult(
			json['verified'], 
			json.get('line'), 
			json.get('column'), 
			json.get('message'),
			json.get('id'))

BreakpointResult.failed = BreakpointResult(False, None, None, None, None)

class BreakpointEvent:
	def __init__(self, reason: str, result: BreakpointResult) -> None:
		self.reason = reason
		self.result = result

	@staticmethod
	def from_json(json) -> 'BreakpointEvent':
		return BreakpointEvent (
			json['reason'],
			BreakpointResult.from_json(json['breakpoint']),
		)

class Module:
	def __init__(self, json: dict):
		self.id = json['id'] # type: Union[int, str]
		self.name = json['name'] # type: str
		self.path = json.get('path') # type: Optional[str]
		self.isOptimized = json.get('isOptimized') # type: Optional[bool]
		self.isUserCode = json.get('isUserCode') # type: Optional[bool]
		self.version = json.get('version') # type: Optional[str]
		self.symbolStatus = json.get('symbolStatus') # type: Optional[str]
		self.symbolFilePath = json.get('symbolFilePath') # type: Optional[str]
		self.dateTimeStamp = json.get('dateTimeStamp') # type: Optional[str]
		self.addressRange = json.get('addressRange') # type: Optional[str]

	@staticmethod
	def from_json(json) -> 'Module':
		return Module(json)

class ModuleEvent:
	none = 0
	new = 1
	changed = 2
	removed = 3
	
	reasons = {'new': new, 'changed': changed, 'removed': removed}

	def __init__(self, json: dict):
		self.reason = ModuleEvent.reasons.get(json['reason'], ModuleEvent.none)
		self.module = Module.from_json(json['module'])

class LoadedSourceEvent:
	none = 0
	new = 1
	changed = 2
	removed = 3
	
	reasons = {'new': new, 'changed': changed, 'removed': removed}

	def __init__(self, json: dict):
		self.reason = LoadedSourceEvent.reasons.get(json['reason'], LoadedSourceEvent.none)
		self.source = Source.from_json(json['source'])

