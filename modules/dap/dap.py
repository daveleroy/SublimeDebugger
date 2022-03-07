from __future__ import annotations
from dataclasses import dataclass

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

@dataclass
class Request:
	type: Literal["request"]
	command: str
	"""The command to execute."""
	arguments: Optional[Any]
	"""Object containing arguments for the command."""

@dataclass
class Event:
	type: Literal["event"]
	event: str
	"""Type of event."""
	body: Optional[Any]
	"""Event-specific information."""

@dataclass
class Response:
	type: Literal["response"]
	request_seq: int
	"""Sequence number of the corresponding request."""
	success: bool
	"""Outcome of the request.\nIf true, the request was successful and the 'body' attribute may contain the result of the request.\nIf the value is false, the attribute 'message' contains the error in short form and the 'body' may contain additional information (see 'ErrorResponse.body.error')."""
	command: str
	"""The command requested."""
	message: Optional[str]
	"""Contains the raw error in short form if 'success' is false.\nThis raw error might be interpreted by the frontend and is not shown in the UI.\nSome predefined values exist."""
	body: Optional[Any]
	"""Contains request result if success is true and optional error details if success is false."""

@dataclass
class CancelArguments:
	"""
	Arguments for 'cancel' request.
	"""
	requestId: Optional[int]
	"""The ID (attribute 'seq') of the request to cancel. If missing no request is cancelled.\nBoth a 'requestId' and a 'progressId' can be specified in one request."""
	progressId: Optional[str]
	"""The ID (attribute 'progressId') of the progress to cancel. If missing no progress is cancelled.\nBoth a 'requestId' and a 'progressId' can be specified in one request."""

@dataclass
class CancelResponse:
	pass

@dataclass
class InitializedEvent:
	pass

@dataclass
class StoppedEvent:
	reason: str
	"""The reason for the event.\nFor backward compatibility this string is shown in the UI if the 'description' attribute is missing (but it must not be translated)."""
	description: Optional[str]
	"""The full reason for the event, e.g. 'Paused on exception'. This string is shown in the UI as is and must be translated."""
	threadId: Optional[int]
	"""The thread which was stopped."""
	preserveFocusHint: Optional[bool]
	"""A value of true hints to the frontend that this event should not change the focus."""
	text: Optional[str]
	"""Additional information. E.g. if reason is 'exception', text contains the exception name. This string is shown in the UI."""
	allThreadsStopped: Optional[bool]
	"""If 'allThreadsStopped' is true, a debug adapter can announce that all threads have stopped.\n- The client should use this information to enable that all threads can be expanded to access their stacktraces.\n- If the attribute is missing or false, only the thread with the given threadId can be expanded."""
	hitBreakpointIds: Optional[List[int]]
	"""Ids of the breakpoints that triggered the event. In most cases there will be only a single breakpoint but here are some examples for multiple breakpoints:\n- Different types of breakpoints map to the same location.\n- Multiple source breakpoints get collapsed to the same instruction by the compiler/runtime.\n- Multiple function breakpoints with different function names map to the same location."""

@dataclass
class ContinuedEvent:
	threadId: int
	"""The thread which was continued."""
	allThreadsContinued: Optional[bool]
	"""If 'allThreadsContinued' is true, a debug adapter can announce that all threads have continued."""

@dataclass
class ExitedEvent:
	exitCode: int
	"""The exit code returned from the debuggee."""

@dataclass
class TerminatedEvent:
	restart: Optional[Any]
	"""A debug adapter may set 'restart' to true (or to an arbitrary object) to request that the front end restarts the session.\nThe value is not interpreted by the client and passed unmodified as an attribute '__restart' to the 'launch' and 'attach' requests."""

@dataclass
class ThreadEvent:
	reason: str
	"""The reason for the event."""
	threadId: int
	"""The identifier of the thread."""

@dataclass
class ProcessEvent:
	name: str
	"""The logical name of the process. This is usually the full path to process's executable file. Example: /home/example/myproj/program.js."""
	systemProcessId: Optional[int]
	"""The system process id of the debugged process. This property will be missing for non-system processes."""
	isLocalProcess: Optional[bool]
	"""If true, the process is running on the same computer as the debug adapter."""
	startMethod: Optional[
		Literal["launch", "attach", "attachForSuspendedLaunch"]
	]
	"""Describes how the debug engine started debugging this process."""
	pointerSize: Optional[int]
	"""The size of a pointer or address for this process, in bits. This value may be used by clients when formatting addresses for display."""

@dataclass
class ProgressStartEvent:
	progressId: str
	"""An ID that must be used in subsequent 'progressUpdate' and 'progressEnd' events to make them refer to the same progress reporting.\nIDs must be unique within a debug session."""
	title: str
	"""Mandatory (short) title of the progress reporting. Shown in the UI to describe the long running operation."""
	requestId: Optional[int]
	"""The request ID that this progress report is related to. If specified a debug adapter is expected to emit\nprogress events for the long running request until the request has been either completed or cancelled.\nIf the request ID is omitted, the progress report is assumed to be related to some general activity of the debug adapter."""
	cancellable: Optional[bool]
	"""If true, the request that reports progress may be canceled with a 'cancel' request.\nSo this property basically controls whether the client should use UX that supports cancellation.\nClients that don't support cancellation are allowed to ignore the setting."""
	message: Optional[str]
	"""Optional, more detailed progress message."""
	percentage: Optional[float]
	"""Optional progress percentage to display (value range: 0 to 100). If omitted no percentage will be shown."""

@dataclass
class ProgressUpdateEvent:
	progressId: str
	"""The ID that was introduced in the initial 'progressStart' event."""
	message: Optional[str]
	"""Optional, more detailed progress message. If omitted, the previous message (if any) is used."""
	percentage: Optional[float]
	"""Optional progress percentage to display (value range: 0 to 100). If omitted no percentage will be shown."""

@dataclass
class ProgressEndEvent:
	progressId: str
	"""The ID that was introduced in the initial 'ProgressStartEvent'."""
	message: Optional[str]
	"""Optional, more detailed progress message. If omitted, the previous message (if any) is used."""

@dataclass
class MemoryEvent:
	memoryReference: str
	"""Memory reference of a memory range that has been updated."""
	offset: int
	"""Starting offset in bytes where memory has been updated. Can be negative."""
	count: int
	"""Number of bytes updated."""

@dataclass
class RunInTerminalRequestArguments:
	"""
	Arguments for 'runInTerminal' request.
	"""
	kind: Optional[Literal["integrated", "external"]]
	"""What kind of terminal to launch."""
	title: Optional[str]
	"""Optional title of the terminal."""
	cwd: str
	"""Working directory for the command. For non-empty, valid paths this typically results in execution of a change directory command."""
	args: List[str]
	"""List of arguments. The first argument is the command to run."""
	env: Optional[Dict[str, Optional[str]]]
	"""Environment key-value pairs that are added to or removed from the default environment."""

@dataclass
class RunInTerminalResponse:
	processId: Optional[int]
	"""The process ID. The value should be less than or equal to 2147483647 (2^31-1)."""
	shellProcessId: Optional[int]
	"""The process ID of the terminal shell. The value should be less than or equal to 2147483647 (2^31-1)."""

@dataclass
class InitializeRequestArguments:
	"""
	Arguments for 'initialize' request.
	"""
	clientID: Optional[str]
	"""The ID of the (frontend) client using this adapter."""
	clientName: Optional[str]
	"""The human readable name of the (frontend) client using this adapter."""
	adapterID: str
	"""The ID of the debug adapter."""
	locale: Optional[str]
	"""The ISO-639 locale of the (frontend) client using this adapter, e.g. en-US or de-CH."""
	linesStartAt1: Optional[bool]
	"""If true all line numbers are 1-based (default)."""
	columnsStartAt1: Optional[bool]
	"""If true all column numbers are 1-based (default)."""
	pathFormat: Optional[str]
	"""Determines in what format paths are specified. The default is 'path', which is the native format."""
	supportsVariableType: Optional[bool]
	"""Client supports the optional type attribute for variables."""
	supportsVariablePaging: Optional[bool]
	"""Client supports the paging of variables."""
	supportsRunInTerminalRequest: Optional[bool]
	"""Client supports the runInTerminal request."""
	supportsMemoryReferences: Optional[bool]
	"""Client supports memory references."""
	supportsProgressReporting: Optional[bool]
	"""Client supports progress reporting."""
	supportsInvalidatedEvent: Optional[bool]
	"""Client supports the invalidated event."""
	supportsMemoryEvent: Optional[bool]
	"""Client supports the memory event."""

@dataclass
class ConfigurationDoneArguments:
	"""
	Arguments for 'configurationDone' request.
	"""
	pass

@dataclass
class ConfigurationDoneResponse:
	pass

@dataclass
class LaunchRequestArguments:
	"""
	Arguments for 'launch' request. Additional attributes are implementation specific.
	"""
	noDebug: Optional[bool]
	"""If noDebug is true the launch request should launch the program without enabling debugging."""
	__restart: Optional[Any]
	"""Optional data from the previous, restarted session.\nThe data is sent as the 'restart' attribute of the 'terminated' event.\nThe client should leave the data intact."""

@dataclass
class LaunchResponse:
	pass

@dataclass
class AttachRequestArguments:
	"""
	Arguments for 'attach' request. Additional attributes are implementation specific.
	"""
	__restart: Optional[Any]
	"""Optional data from the previous, restarted session.\nThe data is sent as the 'restart' attribute of the 'terminated' event.\nThe client should leave the data intact."""

@dataclass
class AttachResponse:
	pass

@dataclass
class RestartArguments:
	"""
	Arguments for 'restart' request.
	"""
	arguments: Optional[Union[LaunchRequestArguments, AttachRequestArguments]]
	"""The latest version of the 'launch' or 'attach' configuration."""

@dataclass
class RestartResponse:
	pass

@dataclass
class DisconnectArguments:
	"""
	Arguments for 'disconnect' request.
	"""
	restart: Optional[bool]
	"""A value of true indicates that this 'disconnect' request is part of a restart sequence."""
	terminateDebuggee: Optional[bool]
	"""Indicates whether the debuggee should be terminated when the debugger is disconnected.\nIf unspecified, the debug adapter is free to do whatever it thinks is best.\nThe attribute is only honored by a debug adapter if the capability 'supportTerminateDebuggee' is true."""
	suspendDebuggee: Optional[bool]
	"""Indicates whether the debuggee should stay suspended when the debugger is disconnected.\nIf unspecified, the debuggee should resume execution.\nThe attribute is only honored by a debug adapter if the capability 'supportSuspendDebuggee' is true."""

@dataclass
class DisconnectResponse:
	pass

@dataclass
class TerminateArguments:
	"""
	Arguments for 'terminate' request.
	"""
	restart: Optional[bool]
	"""A value of true indicates that this 'terminate' request is part of a restart sequence."""

@dataclass
class TerminateResponse:
	pass

@dataclass
class DataBreakpointInfoArguments:
	"""
	Arguments for 'dataBreakpointInfo' request.
	"""
	variablesReference: Optional[int]
	"""Reference to the Variable container if the data breakpoint is requested for a child of the container."""
	name: str
	"""The name of the Variable's child to obtain data breakpoint information for.\nIf variablesReference isn’t provided, this can be an expression."""

@dataclass
class ContinueArguments:
	"""
	Arguments for 'continue' request.
	"""
	threadId: int
	"""Continue execution for the specified thread (if possible).\nIf the backend cannot continue on a single thread but will continue on all threads, it should set the 'allThreadsContinued' attribute in the response to true."""

@dataclass
class ContinueResponse:
	allThreadsContinued: Optional[bool]
	"""If true, the 'continue' request has ignored the specified thread and continued all threads instead.\nIf this attribute is missing a value of 'true' is assumed for backward compatibility."""

@dataclass
class NextResponse:
	pass

@dataclass
class StepInResponse:
	pass

@dataclass
class StepOutResponse:
	pass

@dataclass
class StepBackResponse:
	pass

@dataclass
class ReverseContinueArguments:
	"""
	Arguments for 'reverseContinue' request.
	"""
	threadId: int
	"""Execute 'reverseContinue' for this thread."""

@dataclass
class ReverseContinueResponse:
	pass

@dataclass
class RestartFrameArguments:
	"""
	Arguments for 'restartFrame' request.
	"""
	frameId: int
	"""Restart this stackframe."""

@dataclass
class RestartFrameResponse:
	pass

@dataclass
class GotoArguments:
	"""
	Arguments for 'goto' request.
	"""
	threadId: int
	"""Set the goto target for this thread."""
	targetId: int
	"""The location where the debuggee will continue to run."""

@dataclass
class GotoResponse:
	pass

@dataclass
class PauseArguments:
	"""
	Arguments for 'pause' request.
	"""
	threadId: int
	"""Pause execution for this thread."""

@dataclass
class PauseResponse:
	pass

@dataclass
class ScopesArguments:
	"""
	Arguments for 'scopes' request.
	"""
	frameId: int
	"""Retrieve the scopes for this stackframe."""

@dataclass
class SetVariableResponse:
	value: str
	"""The new value of the variable."""
	type: Optional[str]
	"""The type of the new value. Typically shown in the UI when hovering over the value."""
	variablesReference: Optional[int]
	"""If variablesReference is > 0, the new value is structured and its children can be retrieved by passing variablesReference to the VariablesRequest.\nThe value should be less than or equal to 2147483647 (2^31-1)."""
	namedVariables: Optional[int]
	"""The number of named child variables.\nThe client can use this optional information to present the variables in a paged UI and fetch them in chunks.\nThe value should be less than or equal to 2147483647 (2^31-1)."""
	indexedVariables: Optional[int]
	"""The number of indexed child variables.\nThe client can use this optional information to present the variables in a paged UI and fetch them in chunks.\nThe value should be less than or equal to 2147483647 (2^31-1)."""

@dataclass
class SourceResponse:
	content: str
	"""Content of the source reference."""
	mimeType: Optional[str]
	"""Optional content type (mime type) of the source."""

@dataclass
class ThreadsRequest:
	command: Literal["threads"]

@dataclass
class TerminateThreadsArguments:
	"""
	Arguments for 'terminateThreads' request.
	"""
	threadIds: Optional[List[int]]
	"""Ids of threads to be terminated."""

@dataclass
class TerminateThreadsResponse:
	pass

@dataclass
class ModulesArguments:
	"""
	Arguments for 'modules' request.
	"""
	startModule: Optional[int]
	"""The index of the first module to return; if omitted modules start at 0."""
	moduleCount: Optional[int]
	"""The number of modules to return. If moduleCount is not specified or 0, all modules are returned."""

@dataclass
class LoadedSourcesArguments:
	"""
	Arguments for 'loadedSources' request.
	"""
	pass

@dataclass
class StepInTargetsArguments:
	"""
	Arguments for 'stepInTargets' request.
	"""
	frameId: int
	"""The stack frame for which to retrieve the possible stepIn targets."""

@dataclass
class CompletionsArguments:
	"""
	Arguments for 'completions' request.
	"""
	frameId: Optional[int]
	"""Returns completions in the scope of this stack frame. If not specified, the completions are returned for the global scope."""
	text: str
	"""One or more source lines. Typically this is the text a user has typed into the debug console before he asked for completion."""
	column: int
	"""The character position for which to determine the completion proposals."""
	line: Optional[int]
	"""An optional line for which to determine the completion proposals. If missing the first line of the text is assumed."""

@dataclass
class ExceptionInfoArguments:
	"""
	Arguments for 'exceptionInfo' request.
	"""
	threadId: int
	"""Thread for which exception information should be retrieved."""

@dataclass
class ReadMemoryArguments:
	"""
	Arguments for 'readMemory' request.
	"""
	memoryReference: str
	"""Memory reference to the base location from which data should be read."""
	offset: Optional[int]
	"""Optional offset (in bytes) to be applied to the reference location before reading data. Can be negative."""
	count: int
	"""Number of bytes to read at the specified location and offset."""

@dataclass
class ReadMemoryResponse:
	address: str
	"""The address of the first byte of data returned.\nTreated as a hex value if prefixed with '0x', or as a decimal value otherwise."""
	unreadableBytes: Optional[int]
	"""The number of unreadable bytes encountered after the last successfully read byte.\nThis can be used to determine the number of bytes that must be skipped before a subsequent 'readMemory' request will succeed."""
	data: Optional[str]
	"""The bytes read from memory, encoded using base64."""

@dataclass
class WriteMemoryArguments:
	"""
	Arguments for 'writeMemory' request.
	"""
	memoryReference: str
	"""Memory reference to the base location to which data should be written."""
	offset: Optional[int]
	"""Optional offset (in bytes) to be applied to the reference location before writing data. Can be negative."""
	allowPartial: Optional[bool]
	"""Optional property to control partial writes. If true, the debug adapter should attempt to write memory even if the entire memory region is not writable. In such a case the debug adapter should stop after hitting the first byte of memory that cannot be written and return the number of bytes written in the response via the 'offset' and 'bytesWritten' properties.\nIf false or missing, a debug adapter should attempt to verify the region is writable before writing, and fail the response if it is not."""
	data: str
	"""Bytes to write, encoded using base64."""

@dataclass
class WriteMemoryResponse:
	offset: Optional[int]
	"""Optional property that should be returned when 'allowPartial' is true to indicate the offset of the first byte of data successfully written. Can be negative."""
	bytesWritten: Optional[int]
	"""Optional property that should be returned when 'allowPartial' is true to indicate the number of bytes starting from address that were successfully written."""

@dataclass
class DisassembleArguments:
	"""
	Arguments for 'disassemble' request.
	"""
	memoryReference: str
	"""Memory reference to the base location containing the instructions to disassemble."""
	offset: Optional[int]
	"""Optional offset (in bytes) to be applied to the reference location before disassembling. Can be negative."""
	instructionOffset: Optional[int]
	"""Optional offset (in instructions) to be applied after the byte offset (if any) before disassembling. Can be negative."""
	instructionCount: int
	"""Number of instructions to disassemble starting at the specified location and offset.\nAn adapter must return exactly this number of instructions - any unavailable instructions should be replaced with an implementation-defined 'invalid instruction' value."""
	resolveSymbols: Optional[bool]
	"""If true, the adapter should attempt to resolve memory addresses and other values to symbolic names."""

@dataclass
class ExceptionBreakpointsFilter:
	"""
	An ExceptionBreakpointsFilter is shown in the UI as an filter option for configuring how exceptions are dealt with.
	"""
	filter: str
	"""The internal ID of the filter option. This value is passed to the 'setExceptionBreakpoints' request."""
	label: str
	"""The name of the filter option. This will be shown in the UI."""
	description: Optional[str]
	"""An optional help text providing additional information about the exception filter. This string is typically shown as a hover and must be translated."""
	default: Optional[bool]
	"""Initial value of the filter option. If not specified a value 'false' is assumed."""
	supportsCondition: Optional[bool]
	"""Controls whether a condition can be specified for this filter option. If false or missing, a condition can not be set."""
	conditionDescription: Optional[str]
	"""An optional help text providing information about the condition. This string is shown as the placeholder text for a text box and must be translated."""

@dataclass
class Message:
	"""
	A structured message object. Used to return errors from requests.
	"""
	id: int
	"""Unique identifier for the message."""
	format: str
	"""A format string for the message. Embedded variables have the form '{name}'.\nIf variable name starts with an underscore character, the variable does not contain user data (PII) and can be safely used for telemetry purposes."""
	variables: Optional[Dict[str, str]]
	"""An object used as a dictionary for looking up the variables in the format string."""
	sendTelemetry: Optional[bool]
	"""If true send to telemetry."""
	showUser: Optional[bool]
	"""If true show user."""
	url: Optional[str]
	"""An optional url where additional information about this message can be found."""
	urlLabel: Optional[str]
	"""An optional label that is presented to the user as the UI for opening the url."""

@dataclass
class Module:
	"""
	A Module object represents a row in the modules view.
	Two attributes are mandatory: an id identifies a module in the modules view and is used in a ModuleEvent for identifying a module for adding, updating or deleting.
	The name is used to minimally render the module in the UI.

	Additional attributes can be added to the module. They will show up in the module View if they have a corresponding ColumnDescriptor.

	To avoid an unnecessary proliferation of additional attributes with similar semantics but different names
	we recommend to re-use attributes from the 'recommended' list below first, and only introduce new attributes if nothing appropriate could be found.
	"""
	id: Union[int, str]
	"""Unique identifier for the module."""
	name: str
	"""A name of the module."""
	path: Optional[str]
	"""optional but recommended attributes.\nalways try to use these first before introducing additional attributes.\n\nLogical full path to the module. The exact definition is implementation defined, but usually this would be a full path to the on-disk file for the module."""
	isOptimized: Optional[bool]
	"""True if the module is optimized."""
	isUserCode: Optional[bool]
	"""True if the module is considered 'user code' by a debugger that supports 'Just My Code'."""
	version: Optional[str]
	"""Version of Module."""
	symbolStatus: Optional[str]
	"""User understandable description of if symbols were found for the module (ex: 'Symbols Loaded', 'Symbols not found', etc."""
	symbolFilePath: Optional[str]
	"""Logical full path to the symbol file. The exact definition is implementation defined."""
	dateTimeStamp: Optional[str]
	"""Module created or modified."""
	addressRange: Optional[str]
	"""Address range covered by this module."""

@dataclass
class ColumnDescriptor:
	"""
	A ColumnDescriptor specifies what module attribute to show in a column of the ModulesView, how to format it,
	and what the column's label should be.
	It is only used if the underlying UI actually supports this level of customization.
	"""
	attributeName: str
	"""Name of the attribute rendered in this column."""
	label: str
	"""Header UI label of column."""
	format: Optional[str]
	"""Format to use for the rendered values in this column. TBD how the format strings looks like."""
	type: Optional[Literal["string", "number", "boolean", "unixTimestampUTC"]]
	"""Datatype of values in this column.  Defaults to 'string' if not specified."""
	width: Optional[int]
	"""Width of this column in characters (hint only)."""

@dataclass
class ModulesViewDescriptor:
	"""
	The ModulesViewDescriptor is the container for all declarative configuration options of a ModuleView.
	For now it only specifies the columns to be shown in the modules view.
	"""
	columns: List[ColumnDescriptor]

@dataclass
class Thread:
	"""
	A Thread
	"""
	id: int
	"""Unique identifier for the thread."""
	name: str
	"""A name of the thread."""

@dataclass
class VariablePresentationHint:
	"""
	Optional properties of a variable that can be used to determine how to render the variable in the UI.
	"""
	kind: Optional[str]
	"""The kind of variable. Before introducing additional values, try to use the listed values."""
	attributes: Optional[List[str]]
	"""Set of attributes represented as an array of strings. Before introducing additional values, try to use the listed values."""
	visibility: Optional[str]
	"""Visibility of variable. Before introducing additional values, try to use the listed values."""

@dataclass
class BreakpointLocation:
	"""
	Properties of a breakpoint location returned from the 'breakpointLocations' request.
	"""
	line: int
	"""Start line of breakpoint location."""
	column: Optional[int]
	"""Optional start column of breakpoint location."""
	endLine: Optional[int]
	"""Optional end line of breakpoint location if the location covers a range."""
	endColumn: Optional[int]
	"""Optional end column of breakpoint location if the location covers a range."""

@dataclass
class SourceBreakpoint:
	"""
	Properties of a breakpoint or logpoint passed to the setBreakpoints request.
	"""
	line: int
	"""The source line of the breakpoint or logpoint."""
	column: Optional[int]
	"""An optional source column of the breakpoint."""
	condition: Optional[str]
	"""An optional expression for conditional breakpoints.\nIt is only honored by a debug adapter if the capability 'supportsConditionalBreakpoints' is true."""
	hitCondition: Optional[str]
	"""An optional expression that controls how many hits of the breakpoint are ignored.\nThe backend is expected to interpret the expression as needed.\nThe attribute is only honored by a debug adapter if the capability 'supportsHitConditionalBreakpoints' is true."""
	logMessage: Optional[str]
	"""If this attribute exists and is non-empty, the backend must not 'break' (stop)\nbut log the message instead. Expressions within {} are interpolated.\nThe attribute is only honored by a debug adapter if the capability 'supportsLogPoints' is true."""

@dataclass
class FunctionBreakpoint:
	"""
	Properties of a breakpoint passed to the setFunctionBreakpoints request.
	"""
	name: str
	"""The name of the function."""
	condition: Optional[str]
	"""An optional expression for conditional breakpoints.\nIt is only honored by a debug adapter if the capability 'supportsConditionalBreakpoints' is true."""
	hitCondition: Optional[str]
	"""An optional expression that controls how many hits of the breakpoint are ignored.\nThe backend is expected to interpret the expression as needed.\nThe attribute is only honored by a debug adapter if the capability 'supportsHitConditionalBreakpoints' is true."""

@dataclass
class DataBreakpoint:
	"""
	Properties of a data breakpoint passed to the setDataBreakpoints request.
	"""
	dataId: str
	"""An id representing the data. This id is returned from the dataBreakpointInfo request."""
	accessType: Optional[Literal["read", "write", "readWrite"]]
	"""The access type of the data."""
	condition: Optional[str] = None
	"""An optional expression for conditional breakpoints."""
	hitCondition: Optional[str] = None
	"""An optional expression that controls how many hits of the breakpoint are ignored.\nThe backend is expected to interpret the expression as needed."""

@dataclass
class InstructionBreakpoint:
	"""
	Properties of a breakpoint passed to the setInstructionBreakpoints request
	"""
	instructionReference: str
	"""The instruction reference of the breakpoint.\nThis should be a memory or instruction pointer reference from an EvaluateResponse, Variable, StackFrame, GotoTarget, or Breakpoint."""
	offset: Optional[int]
	"""An optional offset from the instruction reference.\nThis can be negative."""
	condition: Optional[str]
	"""An optional expression for conditional breakpoints.\nIt is only honored by a debug adapter if the capability 'supportsConditionalBreakpoints' is true."""
	hitCondition: Optional[str]
	"""An optional expression that controls how many hits of the breakpoint are ignored.\nThe backend is expected to interpret the expression as needed.\nThe attribute is only honored by a debug adapter if the capability 'supportsHitConditionalBreakpoints' is true."""

@dataclass
class SteppingGranularity(Enum):
	"""
	The granularity of one 'step' in the stepping requests 'next', 'stepIn', 'stepOut', and 'stepBack'.
	"""
	statement = "statement"
	line = "line"
	instruction = "instruction"

@dataclass
class StepInTarget:
	"""
	A StepInTarget can be used in the 'stepIn' request and determines into which single target the stepIn request should step.
	"""
	id: int
	"""Unique identifier for a stepIn target."""
	label: str
	"""The name of the stepIn target (shown in the UI)."""

@dataclass
class GotoTarget:
	"""
	A GotoTarget describes a code location that can be used as a target in the 'goto' request.
	The possible goto targets can be determined via the 'gotoTargets' request.
	"""
	id: int
	"""Unique identifier for a goto target. This is used in the goto request."""
	label: str
	"""The name of the goto target (shown in the UI)."""
	line: int
	"""The line of the goto target."""
	column: Optional[int]
	"""An optional column of the goto target."""
	endLine: Optional[int]
	"""An optional end line of the range covered by the goto target."""
	endColumn: Optional[int]
	"""An optional end column of the range covered by the goto target."""
	instructionPointerReference: Optional[str]
	"""Optional memory reference for the instruction pointer value represented by this target."""

@dataclass
class CompletionItemType(Enum):
	"""
	Some predefined types for the CompletionItem. Please note that not all clients have specific icons for all of them.
	"""
	method = "method"
	function = "function"
	constructor = "constructor"
	field = "field"
	variable = "variable"
	class_ = "class"
	interface = "interface"
	module = "module"
	property = "property"
	unit = "unit"
	# value = "value"
	enum = "enum"
	keyword = "keyword"
	snippet = "snippet"
	text = "text"
	color = "color"
	file = "file"
	reference = "reference"
	customcolor = "customcolor"

@dataclass
class ChecksumAlgorithm(Enum):
	"""
	Names of checksum algorithms that may be supported by a debug adapter.
	"""
	MD5 = "MD5"
	SHA1 = "SHA1"
	SHA256 = "SHA256"
	timestamp = "timestamp"

@dataclass
class Checksum:
	"""
	The checksum of an item calculated by the specified algorithm.
	"""
	algorithm: ChecksumAlgorithm
	"""The algorithm used to calculate this checksum."""
	checksum: str
	"""Value of the checksum."""

@dataclass
class ValueFormat:
	"""
	Provides formatting information for a value.
	"""
	hex: Optional[bool]
	"""Display the value in hex."""

@dataclass
class StackFrameFormat(ValueFormat):
	parameters: Optional[bool]
	"""Displays parameters for the stack frame."""
	parameterTypes: Optional[bool]
	"""Displays the types of parameters for the stack frame."""
	parameterNames: Optional[bool]
	"""Displays the names of parameters for the stack frame."""
	parameterValues: Optional[bool]
	"""Displays the values of parameters for the stack frame."""
	line: Optional[bool]
	"""Displays the line number of the stack frame."""
	module: Optional[bool]
	"""Displays the module of the stack frame."""
	includeAll: Optional[bool]
	"""Includes all stack frames, including those the debug adapter might otherwise hide."""

@dataclass
class ExceptionFilterOptions:
	"""
	An ExceptionFilterOptions is used to specify an exception filter together with a condition for the setExceptionsFilter request.
	"""
	filterId: str
	"""ID of an exception filter returned by the 'exceptionBreakpointFilters' capability."""
	condition: Optional[str]
	"""An optional expression for conditional exceptions.\nThe exception will break into the debugger if the result of the condition is true."""

@dataclass
class ExceptionBreakMode(Enum):
	"""
	This enumeration defines all possible conditions when a thrown exception should result in a break.
	never: never breaks,
	always: always breaks,
	unhandled: breaks when exception unhandled,
	userUnhandled: breaks if the exception is not handled by user code.
	"""
	never = "never"
	always = "always"
	unhandled = "unhandled"
	userUnhandled = "userUnhandled"

@dataclass
class ExceptionPathSegment:
	"""
	An ExceptionPathSegment represents a segment in a path that is used to match leafs or nodes in a tree of exceptions.
	If a segment consists of more than one name, it matches the names provided if 'negate' is false or missing or
	it matches anything except the names provided if 'negate' is true.
	"""
	negate: Optional[bool]
	"""If false or missing this segment matches the names provided, otherwise it matches anything except the names provided."""
	names: List[str]
	"""Depending on the value of 'negate' the names that should match or not match."""

@dataclass
class ExceptionDetails:
	"""
	Detailed information about an exception that has occurred.
	"""
	message: Optional[str]
	"""Message contained in the exception."""
	typeName: Optional[str]
	"""Short type name of the exception object."""
	fullTypeName: Optional[str]
	"""Fully-qualified type name of the exception object."""
	evaluateName: Optional[str]
	"""Optional expression that can be evaluated in the current scope to obtain the exception object."""
	stackTrace: Optional[str]
	"""Stack trace at the time the exception was thrown."""
	innerException: Optional[List[ExceptionDetails]]
	"""Details of the exception contained by this exception, if any."""

@dataclass
class InvalidatedAreas:
	__root__: str
	"""Logical areas that can be invalidated by the 'invalidated' event."""

@dataclass
class ErrorResponse:
	error: Optional[Message]
	"""An optional, structured error message."""

@dataclass
class CancelRequest:
	command: Literal["cancel"]
	arguments: Optional[CancelArguments]

@dataclass
class ModuleEvent:
	reason: Literal["new", "changed", "removed"]
	"""The reason for the event."""
	module: Module
	"""The new, changed, or removed module. In case of 'removed' only the module id is used."""

@dataclass
class InvalidatedEvent:
	areas: Optional[List[InvalidatedAreas]]
	"""Optional set of logical areas that got invalidated. This property has a hint characteristic: a client can only be expected to make a 'best effort' in honouring the areas but there are no guarantees. If this property is missing, empty, or if values are not understand the client should assume a single value 'all'."""
	threadId: Optional[int]
	"""If specified, the client only needs to refetch data related to this thread."""
	stackFrameId: Optional[int]
	"""If specified, the client only needs to refetch data related to this stack frame (and the 'threadId' is ignored)."""

@dataclass
class RunInTerminalRequest:
	command: Literal["runInTerminal"]
	arguments: RunInTerminalRequestArguments

@dataclass
class InitializeRequest:
	command: Literal["initialize"]
	arguments: InitializeRequestArguments

@dataclass
class ConfigurationDoneRequest:
	command: Literal["configurationDone"]
	arguments: Optional[ConfigurationDoneArguments]

@dataclass
class LaunchRequest:
	command: Literal["launch"]
	arguments: LaunchRequestArguments

@dataclass
class AttachRequest:
	command: Literal["attach"]
	arguments: AttachRequestArguments

@dataclass
class RestartRequest:
	command: Literal["restart"]
	arguments: Optional[RestartArguments]

@dataclass
class DisconnectRequest:
	command: Literal["disconnect"]
	arguments: Optional[DisconnectArguments]

@dataclass
class TerminateRequest:
	command: Literal["terminate"]
	arguments: Optional[TerminateArguments]

@dataclass
class BreakpointLocationsResponse:
	breakpoints: List[BreakpointLocation]
	"""Sorted set of possible breakpoint locations."""

@dataclass
class SetFunctionBreakpointsArguments:
	"""
	Arguments for 'setFunctionBreakpoints' request.
	"""
	breakpoints: List[FunctionBreakpoint]
	"""The function names of the breakpoints."""

@dataclass
class DataBreakpointInfoRequest:
	command: Literal["dataBreakpointInfo"]
	arguments: DataBreakpointInfoArguments

@dataclass
class DataBreakpointInfoResponse:
	dataId: Optional[str]
	"""An identifier for the data on which a data breakpoint can be registered with the setDataBreakpoints request or null if no data breakpoint is available."""
	description: str
	"""UI string that describes on what data the breakpoint is set on or why a data breakpoint is not available."""
	accessTypes: Optional[List[Literal["read", "write", "readWrite"]]]
	"""Optional attribute listing the available access types for a potential data breakpoint. A UI frontend could surface this information."""
	canPersist: Optional[bool]
	"""Optional attribute indicating that a potential data breakpoint could be persisted across sessions."""

@dataclass
class SetDataBreakpointsArguments:
	"""
	Arguments for 'setDataBreakpoints' request.
	"""
	breakpoints: List[DataBreakpoint]
	"""The contents of this array replaces all existing data breakpoints. An empty array clears all data breakpoints."""

@dataclass
class SetInstructionBreakpointsArguments:
	"""
	Arguments for 'setInstructionBreakpoints' request
	"""
	breakpoints: List[InstructionBreakpoint]
	"""The instruction references of the breakpoints"""

@dataclass
class ContinueRequest:
	command: Literal["continue"]
	arguments: ContinueArguments

@dataclass
class NextArguments:
	"""
	Arguments for 'next' request.
	"""
	threadId: int
	"""Execute 'next' for this thread."""
	granularity: Optional[SteppingGranularity]
	"""Optional granularity to step. If no granularity is specified, a granularity of 'statement' is assumed."""

@dataclass
class StepInArguments:
	"""
	Arguments for 'stepIn' request.
	"""
	threadId: int
	"""Execute 'stepIn' for this thread."""
	targetId: Optional[int]
	"""Optional id of the target to step into."""
	granularity: Optional[SteppingGranularity]
	"""Optional granularity to step. If no granularity is specified, a granularity of 'statement' is assumed."""

@dataclass
class StepOutArguments:
	"""
	Arguments for 'stepOut' request.
	"""
	threadId: int
	"""Execute 'stepOut' for this thread."""
	granularity: Optional[SteppingGranularity]
	"""Optional granularity to step. If no granularity is specified, a granularity of 'statement' is assumed."""

@dataclass
class StepBackArguments:
	"""
	Arguments for 'stepBack' request.
	"""
	threadId: int
	"""Execute 'stepBack' for this thread."""
	granularity: Optional[SteppingGranularity]
	"""Optional granularity to step. If no granularity is specified, a granularity of 'statement' is assumed."""

@dataclass
class ReverseContinueRequest:
	command: Literal["reverseContinue"]
	arguments: ReverseContinueArguments

@dataclass
class RestartFrameRequest:
	command: Literal["restartFrame"]
	arguments: RestartFrameArguments

@dataclass
class GotoRequest:
	command: Literal["goto"]
	arguments: GotoArguments

@dataclass
class PauseRequest:
	command: Literal["pause"]
	arguments: PauseArguments

@dataclass
class StackTraceArguments:
	"""
	Arguments for 'stackTrace' request.
	"""
	threadId: int
	"""Retrieve the stacktrace for this thread."""
	startFrame: Optional[int]
	"""The index of the first frame to return; if omitted frames start at 0."""
	levels: Optional[int]
	"""The maximum number of frames to return. If levels is not specified or 0, all frames are returned."""
	format: Optional[StackFrameFormat]
	"""Specifies details on how to format the stack frames.\nThe attribute is only honored by a debug adapter if the capability 'supportsValueFormattingOptions' is true."""

@dataclass
class ScopesRequest:
	command: Literal["scopes"]
	arguments: ScopesArguments

@dataclass
class VariablesArguments:
	"""
	Arguments for 'variables' request.
	"""
	variablesReference: int
	"""The Variable reference."""
	filter: Optional[Literal["indexed", "named"]]
	"""Optional filter to limit the child variables to either named or indexed. If omitted, both types are fetched."""
	start: Optional[int]
	"""The index of the first variable to return; if omitted children start at 0."""
	count: Optional[int]
	"""The number of variables to return. If count is missing or 0, all variables are returned."""
	format: Optional[ValueFormat]
	"""Specifies details on how to format the Variable values.\nThe attribute is only honored by a debug adapter if the capability 'supportsValueFormattingOptions' is true."""

@dataclass
class SetVariableArguments:
	"""
	Arguments for 'setVariable' request.
	"""
	variablesReference: int
	"""The reference of the variable container."""
	name: str
	"""The name of the variable in the container."""
	value: str
	"""The value of the variable."""
	format: Optional[ValueFormat]
	"""Specifies details on how to format the response value."""

@dataclass
class ThreadsResponse:
	threads: List[Thread]
	"""All threads."""

@dataclass
class TerminateThreadsRequest:
	command: Literal["terminateThreads"]
	arguments: TerminateThreadsArguments

@dataclass
class ModulesRequest:
	command: Literal["modules"]
	arguments: ModulesArguments

@dataclass
class ModulesResponse:
	modules: List[Module]
	"""All modules or range of modules."""
	totalModules: Optional[int]
	"""The total number of modules available."""

@dataclass
class LoadedSourcesRequest:
	command: Literal["loadedSources"]
	arguments: Optional[LoadedSourcesArguments]

@dataclass
class EvaluateArguments:
	"""
	Arguments for 'evaluate' request.
	"""
	expression: str
	"""The expression to evaluate."""
	frameId: Optional[int]
	"""Evaluate the expression in the scope of this stack frame. If not specified, the expression is evaluated in the global scope."""
	context: Optional[str]
	"""The context in which the evaluate request is run."""
	format: Optional[ValueFormat]
	"""Specifies details on how to format the Evaluate result.\nThe attribute is only honored by a debug adapter if the capability 'supportsValueFormattingOptions' is true."""

@dataclass
class EvaluateResponse:
	result: str
	"""The result of the evaluate request."""
	type: Optional[str]
	"""The optional type of the evaluate result.\nThis attribute should only be returned by a debug adapter if the client has passed the value true for the 'supportsVariableType' capability of the 'initialize' request."""
	presentationHint: Optional[VariablePresentationHint]
	"""Properties of a evaluate result that can be used to determine how to render the result in the UI."""
	variablesReference: int
	"""If variablesReference is > 0, the evaluate result is structured and its children can be retrieved by passing variablesReference to the VariablesRequest.\nThe value should be less than or equal to 2147483647 (2^31-1)."""
	namedVariables: Optional[int]
	"""The number of named child variables.\nThe client can use this optional information to present the variables in a paged UI and fetch them in chunks.\nThe value should be less than or equal to 2147483647 (2^31-1)."""
	indexedVariables: Optional[int]
	"""The number of indexed child variables.\nThe client can use this optional information to present the variables in a paged UI and fetch them in chunks.\nThe value should be less than or equal to 2147483647 (2^31-1)."""
	memoryReference: Optional[str]
	"""Optional memory reference to a location appropriate for this result.\nFor pointer type eval results, this is generally a reference to the memory address contained in the pointer.\nThis attribute should be returned by a debug adapter if the client has passed the value true for the 'supportsMemoryReferences' capability of the 'initialize' request."""

@dataclass
class SetExpressionArguments:
	"""
	Arguments for 'setExpression' request.
	"""
	expression: str
	"""The l-value expression to assign to."""
	value: str
	"""The value expression to assign to the l-value expression."""
	frameId: Optional[int]
	"""Evaluate the expressions in the scope of this stack frame. If not specified, the expressions are evaluated in the global scope."""
	format: Optional[ValueFormat]
	"""Specifies how the resulting value should be formatted."""

@dataclass
class SetExpressionResponse:
	value: str
	"""The new value of the expression."""
	type: Optional[str]
	"""The optional type of the value.\nThis attribute should only be returned by a debug adapter if the client has passed the value true for the 'supportsVariableType' capability of the 'initialize' request."""
	presentationHint: Optional[VariablePresentationHint]
	"""Properties of a value that can be used to determine how to render the result in the UI."""
	variablesReference: Optional[int]
	"""If variablesReference is > 0, the value is structured and its children can be retrieved by passing variablesReference to the VariablesRequest.\nThe value should be less than or equal to 2147483647 (2^31-1)."""
	namedVariables: Optional[int]
	"""The number of named child variables.\nThe client can use this optional information to present the variables in a paged UI and fetch them in chunks.\nThe value should be less than or equal to 2147483647 (2^31-1)."""
	indexedVariables: Optional[int]
	"""The number of indexed child variables.\nThe client can use this optional information to present the variables in a paged UI and fetch them in chunks.\nThe value should be less than or equal to 2147483647 (2^31-1)."""

@dataclass
class StepInTargetsRequest:
	command: Literal["stepInTargets"]
	arguments: StepInTargetsArguments

@dataclass
class StepInTargetsResponse:
	targets: List[StepInTarget]
	"""The possible stepIn targets of the specified source location."""

@dataclass
class GotoTargetsResponse:
	targets: List[GotoTarget]
	"""The possible goto targets of the specified location."""

@dataclass
class CompletionsRequest:
	command: Literal["completions"]
	arguments: CompletionsArguments

@dataclass
class ExceptionInfoRequest:
	command: Literal["exceptionInfo"]
	arguments: ExceptionInfoArguments

@dataclass
class ExceptionInfoResponse:
	body: ExceptionInfoResponseBody

@dataclass
class ExceptionInfoResponseBody:
	exceptionId: str
	"""ID of the exception that was thrown."""
	description: Optional[str]
	"""Descriptive text for the exception provided by the debug adapter."""
	breakMode: ExceptionBreakMode
	"""Mode that caused the exception notification to be raised."""
	details: Optional[ExceptionDetails]
	"""Detailed information about the exception."""

@dataclass
class ReadMemoryRequest:
	command: Literal["readMemory"]
	arguments: ReadMemoryArguments

@dataclass
class WriteMemoryRequest:
	command: Literal["writeMemory"]
	arguments: WriteMemoryArguments

@dataclass
class DisassembleRequest:
	command: Literal["disassemble"]
	arguments: DisassembleArguments

@dataclass
class Capabilities:
	"""
	Information about the capabilities of a debug adapter.
	"""
	supportsConfigurationDoneRequest: Optional[bool] = None
	"""The debug adapter supports the 'configurationDone' request."""
	supportsFunctionBreakpoints: Optional[bool] = None
	"""The debug adapter supports function breakpoints."""
	supportsConditionalBreakpoints: Optional[bool] = None
	"""The debug adapter supports conditional breakpoints."""
	supportsHitConditionalBreakpoints: Optional[bool] = None
	"""The debug adapter supports breakpoints that break execution after a specified number of hits."""
	supportsEvaluateForHovers: Optional[bool] = None
	"""The debug adapter supports a (side effect free) evaluate request for data hovers."""
	exceptionBreakpointFilters: Optional[List[ExceptionBreakpointsFilter]] = None
	"""Available exception filter options for the 'setExceptionBreakpoints' request."""
	supportsStepBack: Optional[bool] = None
	"""The debug adapter supports stepping back via the 'stepBack' and 'reverseContinue' requests."""
	supportsSetVariable: Optional[bool] = None
	"""The debug adapter supports setting a variable to a value."""
	supportsRestartFrame: Optional[bool] = None
	"""The debug adapter supports restarting a frame."""
	supportsGotoTargetsRequest: Optional[bool] = None
	"""The debug adapter supports the 'gotoTargets' request."""
	supportsStepInTargetsRequest: Optional[bool] = None
	"""The debug adapter supports the 'stepInTargets' request."""
	supportsCompletionsRequest: Optional[bool] = None
	"""The debug adapter supports the 'completions' request."""
	completionTriggerCharacters: Optional[List[str]] = None
	"""The set of characters that should trigger completion in a REPL. If not specified, the UI should assume the '.' character."""
	supportsModulesRequest: Optional[bool] = None
	"""The debug adapter supports the 'modules' request."""
	additionalModuleColumns: Optional[List[ColumnDescriptor]] = None
	"""The set of additional module information exposed by the debug adapter."""
	supportedChecksumAlgorithms: Optional[List[ChecksumAlgorithm]] = None
	"""Checksum algorithms supported by the debug adapter."""
	supportsRestartRequest: Optional[bool] = None
	"""The debug adapter supports the 'restart' request. In this case a client should not implement 'restart' by terminating and relaunching the adapter but by calling the RestartRequest."""
	supportsExceptionOptions: Optional[bool] = None
	"""The debug adapter supports 'exceptionOptions' on the setExceptionBreakpoints request."""
	supportsValueFormattingOptions: Optional[bool] = None
	"""The debug adapter supports a 'format' attribute on the stackTraceRequest, variablesRequest, and evaluateRequest."""
	supportsExceptionInfoRequest: Optional[bool] = None
	"""The debug adapter supports the 'exceptionInfo' request."""
	supportTerminateDebuggee: Optional[bool] = None
	"""The debug adapter supports the 'terminateDebuggee' attribute on the 'disconnect' request."""
	supportSuspendDebuggee: Optional[bool] = None
	"""The debug adapter supports the 'suspendDebuggee' attribute on the 'disconnect' request."""
	supportsDelayedStackTraceLoading: Optional[bool] = None
	"""The debug adapter supports the delayed loading of parts of the stack, which requires that both the 'startFrame' and 'levels' arguments and an optional 'totalFrames' result of the 'StackTrace' request are supported."""
	supportsLoadedSourcesRequest: Optional[bool] = None
	"""The debug adapter supports the 'loadedSources' request."""
	supportsLogPoints: Optional[bool] = None
	"""The debug adapter supports logpoints by interpreting the 'logMessage' attribute of the SourceBreakpoint."""
	supportsTerminateThreadsRequest: Optional[bool] = None
	"""The debug adapter supports the 'terminateThreads' request."""
	supportsSetExpression: Optional[bool] = None
	"""The debug adapter supports the 'setExpression' request."""
	supportsTerminateRequest: Optional[bool] = None
	"""The debug adapter supports the 'terminate' request."""
	supportsDataBreakpoints: Optional[bool] = None
	"""The debug adapter supports data breakpoints."""
	supportsReadMemoryRequest: Optional[bool] = None
	"""The debug adapter supports the 'readMemory' request."""
	supportsWriteMemoryRequest: Optional[bool] = None
	"""The debug adapter supports the 'writeMemory' request."""
	supportsDisassembleRequest: Optional[bool] = None
	"""The debug adapter supports the 'disassemble' request."""
	supportsCancelRequest: Optional[bool] = None
	"""The debug adapter supports the 'cancel' request."""
	supportsBreakpointLocationsRequest: Optional[bool] = None
	"""The debug adapter supports the 'breakpointLocations' request."""
	supportsClipboardContext: Optional[bool] = None
	"""The debug adapter supports the 'clipboard' context value in the 'evaluate' request."""
	supportsSteppingGranularity: Optional[bool] = None
	"""The debug adapter supports stepping granularities (argument 'granularity') for the stepping requests."""
	supportsInstructionBreakpoints: Optional[bool] = None
	"""The debug adapter supports adding breakpoints based on instruction references."""
	supportsExceptionFilterOptions: Optional[bool] = None
	"""The debug adapter supports 'filterOptions' as an argument on the 'setExceptionBreakpoints' request."""

@dataclass
class Source:
	"""
	A Source is a descriptor for source code.
	It is returned from the debug adapter as part of a StackFrame and it is used by clients when specifying breakpoints.
	"""
	name: Optional[str] = None
	"""The short name of the source. Every source returned from the debug adapter has a name.\nWhen sending a source to the debug adapter this name is optional."""
	path: Optional[str] = None
	"""The path of the source to be shown in the UI.\nIt is only used to locate and load the content of the source if no sourceReference is specified (or its value is 0)."""
	sourceReference: Optional[int] = None
	"""If sourceReference > 0 the contents of the source must be retrieved through the SourceRequest (even if a path is specified).\nA sourceReference is only valid for a session, so it must not be used to persist a source.\nThe value should be less than or equal to 2147483647 (2^31-1)."""
	presentationHint: Optional[Literal["normal", "emphasize", "deemphasize"]] = None
	"""An optional hint for how to present the source in the UI.\nA value of 'deemphasize' can be used to indicate that the source is not available or that it is skipped on stepping."""
	origin: Optional[str] = None
	"""The (optional) origin of this source: possible values 'internal module', 'inlined content from source map', etc."""
	sources: Optional[List[Source]] = None
	"""An optional list of sources that are related to this source. These may be the source that generated this source."""
	adapterData: Optional[Any] = None
	"""Optional data that a debug adapter might want to loop through the client.\nThe client should leave the data intact and persist it across sessions. The client should not interpret the data."""
	checksums: Optional[List[Checksum]] = None
	"""The checksums associated with this file."""

@dataclass
class StackFrame:
	"""
	A Stackframe contains the source location.
	"""
	id: int
	"""An identifier for the stack frame. It must be unique across all threads.\nThis id can be used to retrieve the scopes of the frame with the 'scopesRequest' or to restart the execution of a stackframe."""
	name: str
	"""The name of the stack frame, typically a method name."""
	source: Optional[Source]
	"""The optional source of the frame."""
	line: int
	"""The line within the file of the frame. If source is null or doesn't exist, line is 0 and must be ignored."""
	column: int
	"""The column within the line. If source is null or doesn't exist, column is 0 and must be ignored."""
	endLine: Optional[int]
	"""An optional end line of the range covered by the stack frame."""
	endColumn: Optional[int]
	"""An optional end column of the range covered by the stack frame."""
	canRestart: Optional[bool]
	"""Indicates whether this frame can be restarted with the 'restart' request. Clients should only use this if the debug adapter supports the 'restart' request (capability 'supportsRestartRequest' is true)."""
	instructionPointerReference: Optional[str]
	"""Optional memory reference for the current instruction pointer in this frame."""
	moduleId: Optional[Union[int, str]]
	"""The module associated with this frame, if any."""
	presentationHint: Optional[Literal["normal", "label", "subtle"]]
	"""An optional hint for how to present this frame in the UI.\nA value of 'label' can be used to indicate that the frame is an artificial frame that is used as a visual label or separator. A value of 'subtle' can be used to change the appearance of a frame in a 'subtle' way."""

@dataclass
class Scope:
	"""
	A Scope is a named container for variables. Optionally a scope can map to a source or a range within a source.
	"""
	name: str
	"""Name of the scope such as 'Arguments', 'Locals', or 'Registers'. This string is shown in the UI as is and can be translated."""
	presentationHint: Optional[str]
	"""An optional hint for how to present this scope in the UI. If this attribute is missing, the scope is shown with a generic UI."""
	variablesReference: int
	"""The variables of this scope can be retrieved by passing the value of variablesReference to the VariablesRequest."""
	namedVariables: Optional[int]
	"""The number of named variables in this scope.\nThe client can use this optional information to present the variables in a paged UI and fetch them in chunks."""
	indexedVariables: Optional[int]
	"""The number of indexed variables in this scope.\nThe client can use this optional information to present the variables in a paged UI and fetch them in chunks."""
	expensive: bool
	"""If true, the number of variables in this scope is large or expensive to retrieve."""
	source: Optional[Source]
	"""Optional source for this scope."""
	line: Optional[int]
	"""Optional start line of the range covered by this scope."""
	column: Optional[int]
	"""Optional start column of the range covered by this scope."""
	endLine: Optional[int]
	"""Optional end line of the range covered by this scope."""
	endColumn: Optional[int]
	"""Optional end column of the range covered by this scope."""

@dataclass
class Variable:
	"""
	A Variable is a name/value pair.
	Optionally a variable can have a 'type' that is shown if space permits or when hovering over the variable's name.
	An optional 'kind' is used to render additional properties of the variable, e.g. different icons can be used to indicate that a variable is public or private.
	If the value is structured (has children), a handle is provided to retrieve the children with the VariablesRequest.
	If the number of named or indexed children is large, the numbers should be returned via the optional 'namedVariables' and 'indexedVariables' attributes.
	The client can use this optional information to present the children in a paged UI and fetch them in chunks.
	"""
	name: str
	"""The variable's name."""
	value: str
	"""The variable's value. This can be a multi-line text, e.g. for a function the body of a function."""
	type: Optional[str]
	"""The type of the variable's value. Typically shown in the UI when hovering over the value.\nThis attribute should only be returned by a debug adapter if the client has passed the value true for the 'supportsVariableType' capability of the 'initialize' request."""
	presentationHint: Optional[VariablePresentationHint]
	"""Properties of a variable that can be used to determine how to render the variable in the UI."""
	evaluateName: Optional[str]
	"""Optional evaluatable name of this variable which can be passed to the 'EvaluateRequest' to fetch the variable's value."""
	variablesReference: int
	"""If variablesReference is > 0, the variable is structured and its children can be retrieved by passing variablesReference to the VariablesRequest."""
	namedVariables: Optional[int]
	"""The number of named child variables.\nThe client can use this optional information to present the children in a paged UI and fetch them in chunks."""
	indexedVariables: Optional[int]
	"""The number of indexed child variables.\nThe client can use this optional information to present the children in a paged UI and fetch them in chunks."""
	memoryReference: Optional[str]
	"""Optional memory reference for the variable if the variable represents executable code, such as a function pointer.\nThis attribute is only required if the client has passed the value true for the 'supportsMemoryReferences' capability of the 'initialize' request."""

@dataclass
class Breakpoint:
	"""
	Information about a Breakpoint created in setBreakpoints, setFunctionBreakpoints, setInstructionBreakpoints, or setDataBreakpoints.
	"""
	id: Optional[int] = None
	"""An optional identifier for the breakpoint. It is needed if breakpoint events are used to update or remove breakpoints."""
	verified: bool = False
	"""If true breakpoint could be set (but not necessarily at the desired location)."""
	message: Optional[str] = None
	"""An optional message about the state of the breakpoint.\nThis is shown to the user and can be used to explain why a breakpoint could not be verified."""
	source: Optional[Source] = None
	"""The source where the breakpoint is located."""
	line: Optional[int] = None
	"""The start line of the actual range covered by the breakpoint."""
	column: Optional[int] = None
	"""An optional start column of the actual range covered by the breakpoint."""
	endLine: Optional[int] = None
	"""An optional end line of the actual range covered by the breakpoint."""
	endColumn: Optional[int] = None
	"""An optional end column of the actual range covered by the breakpoint.\nIf no end line is given, then the end column is assumed to be in the start line."""
	instructionReference: Optional[str] = None
	"""An optional memory reference to where the breakpoint is set."""
	offset: Optional[int] = None
	"""An optional offset from the instruction reference.\nThis can be negative."""

@dataclass
class CompletionItem:
	"""
	CompletionItems are the suggestions returned from the CompletionsRequest.
	"""
	label: str
	"""The label of this completion item. By default this is also the text that is inserted when selecting this completion."""
	text: Optional[str]
	"""If text is not falsy then it is inserted instead of the label."""
	sortText: Optional[str]
	"""A human-readable string with additional information about this item, like type or symbol information."""
	detail: Optional[str]
	"""A string that should be used when comparing this item with other items. When `falsy` the label is used."""
	type: Optional[CompletionItemType]
	"""The item's type. Typically the client uses this information to render the item in the UI with an icon."""
	start: Optional[int]
	"""This value determines the location (in the CompletionsRequest's 'text' attribute) where the completion text is added.\nIf missing the text is added at the location specified by the CompletionsRequest's 'column' attribute."""
	length: Optional[int]
	"""This value determines how many characters are overwritten by the completion text.\nIf missing the value 0 is assumed which results in the completion text being inserted."""
	selectionStart: Optional[int]
	"""Determines the start of the new selection after the text has been inserted (or replaced).\nThe start position must in the range 0 and length of the completion text.\nIf omitted the selection starts at the end of the completion text."""
	selectionLength: Optional[int]
	"""Determines the length of the new selection after the text has been inserted (or replaced).\nThe selection can not extend beyond the bounds of the completion text.\nIf omitted the length is assumed to be 0."""

@dataclass
class ExceptionOptions:
	"""
	An ExceptionOptions assigns configuration options to a set of exceptions.
	"""
	path: Optional[List[ExceptionPathSegment]]
	"""A path that selects a single or multiple exceptions in a tree. If 'path' is missing, the whole tree is selected.\nBy convention the first segment of the path is a category that is used to group exceptions in the UI."""
	breakMode: ExceptionBreakMode
	"""Condition when a thrown exception should result in a break."""

@dataclass
class DisassembledInstruction:
	"""
	Represents a single disassembled instruction.
	"""
	address: str
	"""The address of the instruction. Treated as a hex value if prefixed with '0x', or as a decimal value otherwise."""
	instructionBytes: Optional[str]
	"""Optional raw bytes representing the instruction and its operands, in an implementation-defined format."""
	instruction: str
	"""Text representing the instruction and its operands, in an implementation-defined format."""
	symbol: Optional[str]
	"""Name of the symbol that corresponds with the location of this instruction, if any."""
	location: Optional[Source]
	"""Source location that corresponds to this instruction, if any.\nShould always be set (if available) on the first instruction returned,\nbut can be omitted afterwards if this instruction maps to the same source file as the previous instruction."""
	line: Optional[int]
	"""The line within the source location that corresponds to this instruction, if any."""
	column: Optional[int]
	"""The column within the line that corresponds to this instruction, if any."""
	endLine: Optional[int]
	"""The end line of the range that corresponds to this instruction, if any."""
	endColumn: Optional[int]
	"""The end column of the range that corresponds to this instruction, if any."""

@dataclass
class OutputEvent:
	output: str
	"""The output to report."""
	category: Optional[str] = None
	"""The output category. If not specified, 'console' is assumed."""
	group: Optional[Literal["start", "startCollapsed", "end"]] = None
	"""Support for keeping an output log organized by grouping related messages."""
	variablesReference: Optional[int] = None
	"""If an attribute 'variablesReference' exists and its value is > 0, the output contains objects which can be retrieved by passing 'variablesReference' to the 'variables' request. The value should be less than or equal to 2147483647 (2^31-1)."""
	source: Optional[Source] = None
	"""An optional source location where the output was produced."""
	line: Optional[int] = None
	"""An optional source location line where the output was produced."""
	column: Optional[int] = None
	"""An optional source location column where the output was produced."""
	data: Optional[Any] = None
	"""Optional data to report. For the 'telemetry' category the data will be sent to telemetry, for the other categories the data is shown in JSON format."""

@dataclass
class BreakpointEvent:
	reason: str
	"""The reason for the event."""
	breakpoint: Breakpoint
	"""The 'id' attribute is used to find the target breakpoint and the other attributes are used as the new values."""

@dataclass
class LoadedSourceEvent:
	reason: Literal["new", "changed", "removed"]
	"""The reason for the event."""
	source: Source
	"""The new, changed, or removed source."""

@dataclass
class CapabilitiesEvent:
	capabilities: Capabilities
	"""The set of updated capabilities."""

@dataclass
class InitializeResponse:
	body: Optional[Capabilities]
	"""The capabilities of this debug adapter."""

@dataclass
class BreakpointLocationsArguments:
	"""
	Arguments for 'breakpointLocations' request.
	"""
	source: Source
	"""The source location of the breakpoints; either 'source.path' or 'source.reference' must be specified."""
	line: int
	"""Start line of range to search possible breakpoint locations in. If only the line is specified, the request returns all possible locations in that line."""
	column: Optional[int]
	"""Optional start column of range to search possible breakpoint locations in. If no start column is given, the first column in the start line is assumed."""
	endLine: Optional[int]
	"""Optional end line of range to search possible breakpoint locations in. If no end line is given, then the end line is assumed to be the start line."""
	endColumn: Optional[int]
	"""Optional end column of range to search possible breakpoint locations in. If no end column is given, then it is assumed to be in the last column of the end line."""

@dataclass
class SetBreakpointsArguments:
	"""
	Arguments for 'setBreakpoints' request.
	"""
	source: Source
	"""The source location of the breakpoints; either 'source.path' or 'source.reference' must be specified."""
	breakpoints: Optional[List[SourceBreakpoint]]
	"""The code locations of the breakpoints."""
	lines: Optional[List[int]]
	"""Deprecated: The code locations of the breakpoints."""
	sourceModified: Optional[bool]
	"""A value of true indicates that the underlying source has been modified which results in new breakpoint locations."""

@dataclass
class SetBreakpointsResponse:
	breakpoints: List[Breakpoint]
	"""Information about the breakpoints.\nThe array elements are in the same order as the elements of the 'breakpoints' (or the deprecated 'lines') array in the arguments."""

@dataclass
class SetFunctionBreakpointsRequest:
	command: Literal["setFunctionBreakpoints"]
	arguments: SetFunctionBreakpointsArguments

@dataclass
class SetFunctionBreakpointsResponse:
	body: SetFunctionBreakpointsResponseBody

@dataclass
class SetFunctionBreakpointsResponseBody:
	breakpoints: List[Breakpoint]
	"""Information about the breakpoints. The array elements correspond to the elements of the 'breakpoints' array."""

@dataclass
class SetExceptionBreakpointsArguments:
	"""
	Arguments for 'setExceptionBreakpoints' request.
	"""
	filters: List[str]
	"""Set of exception filters specified by their ID. The set of all possible exception filters is defined by the 'exceptionBreakpointFilters' capability. The 'filter' and 'filterOptions' sets are additive."""
	filterOptions: Optional[List[ExceptionFilterOptions]]
	"""Set of exception filters and their options. The set of all possible exception filters is defined by the 'exceptionBreakpointFilters' capability. This attribute is only honored by a debug adapter if the capability 'supportsExceptionFilterOptions' is true. The 'filter' and 'filterOptions' sets are additive."""
	exceptionOptions: Optional[List[ExceptionOptions]]
	"""Configuration options for selected exceptions.\nThe attribute is only honored by a debug adapter if the capability 'supportsExceptionOptions' is true."""

@dataclass
class SetExceptionBreakpointsResponse:
	breakpoints: Optional[List[Breakpoint]]
	"""Information about the exception breakpoints or filters.\nThe breakpoints returned are in the same order as the elements of the 'filters', 'filterOptions', 'exceptionOptions' arrays in the arguments. If both 'filters' and 'filterOptions' are given, the returned array must start with 'filters' information first, followed by 'filterOptions' information."""

@dataclass
class SetDataBreakpointsRequest:
	command: Literal["setDataBreakpoints"]
	arguments: SetDataBreakpointsArguments

@dataclass
class SetDataBreakpointsResponse:
	breakpoints: List[Breakpoint]
	"""Information about the data breakpoints. The array elements correspond to the elements of the input argument 'breakpoints' array."""

@dataclass
class SetInstructionBreakpointsRequest:
	command: Literal["setInstructionBreakpoints"]
	arguments: SetInstructionBreakpointsArguments

@dataclass
class SetInstructionBreakpointsResponse:
	breakpoints: List[Breakpoint]
	"""Information about the breakpoints. The array elements correspond to the elements of the 'breakpoints' array."""

@dataclass
class NextRequest:
	command: Literal["next"]
	arguments: NextArguments

@dataclass
class StepInRequest:
	command: Literal["stepIn"]
	arguments: StepInArguments

@dataclass
class StepOutRequest:
	command: Literal["stepOut"]
	arguments: StepOutArguments

@dataclass
class StepBackRequest:
	command: Literal["stepBack"]
	arguments: StepBackArguments

@dataclass
class StackTraceRequest:
	command: Literal["stackTrace"]
	arguments: StackTraceArguments

@dataclass
class StackTraceResponse:
	stackFrames: List[StackFrame]
	"""The frames of the stackframe. If the array has length zero, there are no stackframes available.\nThis means that there is no location information available."""
	totalFrames: Optional[int]
	"""The total number of frames available in the stack. If omitted or if totalFrames is larger than the available frames, a client is expected to request frames until a request returns less frames than requested (which indicates the end of the stack). Returning monotonically increasing totalFrames values for subsequent requests can be used to enforce paging in the client."""

@dataclass
class ScopesResponse:
	scopes: List[Scope]
	"""The scopes of the stackframe. If the array has length zero, there are no scopes available."""

@dataclass
class VariablesRequest:
	command: Literal["variables"]
	arguments: VariablesArguments

@dataclass
class VariablesResponse:
	variables: List[Variable]
	"""All (or a range) of variables for the given variable reference."""

@dataclass
class SetVariableRequest:
	command: Literal["setVariable"]
	arguments: SetVariableArguments

@dataclass
class SourceArguments:
	"""
	Arguments for 'source' request.
	"""
	source: Optional[Source]
	"""Specifies the source content to load. Either source.path or source.sourceReference must be specified."""
	sourceReference: int
	"""The reference to the source. This is the same as source.sourceReference.\nThis is provided for backward compatibility since old backends do not understand the 'source' attribute."""

@dataclass
class LoadedSourcesResponse:
	sources: List[Source]
	"""Set of loaded sources."""

@dataclass
class EvaluateRequest:
	command: Literal["evaluate"]
	arguments: EvaluateArguments

@dataclass
class SetExpressionRequest:
	command: Literal["setExpression"]
	arguments: SetExpressionArguments

@dataclass
class CompletionsResponse:
	body: CompletionsResponseBody

@dataclass
class CompletionsResponseBody:
	targets: List[CompletionItem]
	"""The possible completions for ."""

@dataclass
class DisassembleResponse:
	body: Optional[DisassembleResponseBody]

@dataclass
class DisassembleResponseBody:
	instructions: List[DisassembledInstruction]
	"""The list of disassembled instructions."""

@dataclass
class BreakpointLocationsRequest:
	command: Literal["breakpointLocations"]
	arguments: Optional[BreakpointLocationsArguments]

@dataclass
class SetBreakpointsRequest:
	command: Literal["setBreakpoints"]
	arguments: SetBreakpointsArguments

@dataclass
class SetExceptionBreakpointsRequest:
	command: Literal["setExceptionBreakpoints"]
	arguments: SetExceptionBreakpointsArguments

@dataclass
class SourceRequest:
	command: Literal["source"]
	arguments: SourceArguments

@dataclass
class GotoTargetsRequest:
	command: Literal["gotoTargets"]
	arguments: GotoTargetsArguments

@dataclass
class GotoTargetsArguments:
	"""
	Arguments for 'gotoTargets' request.
	"""
	source: Source
	"""The source location for which the goto targets are determined."""
	line: int
	"""The line location for which the goto targets are determined."""
	column: Optional[int]
	"""An optional column location for which the goto targets are determined."""
