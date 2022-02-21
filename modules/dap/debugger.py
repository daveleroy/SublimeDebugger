from __future__ import annotations
from ..typecheck import *

from ..import core

if TYPE_CHECKING:
	from .configuration import AdapterConfiguration, ConfigurationExpanded
	from ..breakpoints import Breakpoints
	from . import Session
	from . import OutputEvent

class Debugger(Protocol):
	on_error: core.Event[str]
	on_info: core.Event[str]

	on_session_added: core.Event[Session]
	on_session_removed: core.Event[Session]
	on_session_active: core.Event[Session]

	on_session_modules_updated: core.Event[Session]
	on_session_sources_updated: core.Event[Session]
	on_session_variables_updated: core.Event[Session]
	on_session_threads_updated: core.Event[Session]
	on_session_state_updated: core.Event[Session, Session.State]
	on_session_output: core.Event[Session, OutputEvent]

	sessions: list[Session]
	session: Session|None

	async def launch(self, breakpoints: Breakpoints, adapter: AdapterConfiguration, configuration: ConfigurationExpanded, restart: Any|None = None, no_debug: bool = False, parent: Session|None = None) -> Session: ...
