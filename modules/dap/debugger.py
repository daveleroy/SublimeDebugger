from __future__ import annotations
from typing import TYPE_CHECKING, Any, Protocol

from .. import core

if TYPE_CHECKING:
	from .adapter import Adapter
	from .configuration import ConfigurationExpanded

	from .breakpoints import Breakpoints
	from . import Session
	from .api import OutputEvent
	from .variable import SourceLocation


class Debugger(Protocol):
	on_session_added: core.Event[Session]
	on_session_removed: core.Event[Session]
	on_session_active: core.Event[Session]
	on_session_thread_or_frame_updated: core.Event[Session]

	on_session_output: core.Event[Session, OutputEvent]
	on_session_updated: core.Event[Session]
	on_session_modules_updated: core.Event[Session]
	on_session_sources_updated: core.Event[Session]
	on_session_variables_updated: core.Event[Session]
	on_session_threads_updated: core.Event[Session]

	sessions: list[Session]
	session: Session | None
	current_session: Session  # same as session but throws if there is no session

	console: Console
	breakpoints: Breakpoints

	async def launch(self, adapter: Adapter, configuration: ConfigurationExpanded, restart: Any | None = None, no_debug: bool = False, parent: Session | None = None) -> Session: ...


class Console(Protocol):
	def error(self, text: str, source: SourceLocation | None = None):
		self.log('error', text, source)

	def warn(self, text: str, source: SourceLocation | None = None):
		self.log('error', text, source)

	def info(self, text: str, source: SourceLocation | None = None):
		self.log('comment', text, source)

	def __call__(self, type: str, value: Any, source: SourceLocation | None = None, session: Session | None = None):
		self.log(type, value, source, session)

	def log(self, type: str, value: Any, source: SourceLocation | None = None, session: Session | None = None): ...


class ConsoleSessionBound(Console):
	def __init__(self, session: Session, console: Console) -> None:
		self.session = session
		self.console = console

	def log(self, type: str, value: Any, source: SourceLocation | None = None, session: Session | None = None):
		self.console.log(type, value, source=source, session=session or self.session)


class StdioLogger(Console):
	def log(self, type: str, value: Any, source: SourceLocation | None = None, session: Session | None = None):
		print(f'Debugger: {type}: {value} ({source} session: {session})')

stdio = StdioLogger()
