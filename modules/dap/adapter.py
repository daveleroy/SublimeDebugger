from __future__ import annotations
from typing import TYPE_CHECKING, Any
import sublime
import re
from .. import core
from .. import dap
from .transport import Transport
from .configuration import Configuration, ConfigurationExpanded, Task, ConfigurationVariables
from .adapter_registry import AdapterRegistery
from .adapter_installer import AdapterInstaller

if TYPE_CHECKING:
	from .session import Session
	from .debugger import Debugger, Console


# See /adapters for examples of how to create an Adapter class
class Adapter(metaclass=AdapterRegistery):
	type: str | list[str]

	@property
	def types(self) -> list[str]:
		return [self.type] if isinstance(self.type, str) else self.type

	@property
	def name(self) -> str:
		return self.type if isinstance(self.type, str) else self.type[0]

	docs: str | None = None
	development: bool = False
	internal: bool = False

	installer = AdapterInstaller()

	async def start(self, console: Console, configuration: ConfigurationExpanded) -> Transport: ...

	@property
	def installed_version(self) -> str | None:
		return self.installer.installed_version()

	@property
	def configuration_snippets(self) -> list[dict[str, Any]]:
		return self.installer.configuration_snippets()

	@property
	def configuration_schema(self) -> dict[str, Any]:
		return self.installer.configuration_schema()

	async def configuration_resolve(self, configuration: ConfigurationExpanded) -> ConfigurationExpanded:
		return configuration

	async def configurations(self, variables: ConfigurationVariables) -> list[Configuration]:
		return []

	async def tasks(self, variables: ConfigurationVariables) -> list[Task]:
		return []

	def on_hover_provider(self, view: sublime.View, point: int) -> tuple[str, sublime.Region] | None:
		word = view.word(point)
		if not word:
			return None

		# for expressions such as `a.b->c`
		# hovering over `a` returns `a`
		# hovering over `b` returns `a.b`
		# hovering over `c` returns `a.b->c`
		line = view.line(word)
		line_up_to_and_including_word = view.substr(sublime.Region(line.a, word.b))
		match = re.search(r'(([\\\$a-zA-Z0-9_])|(->)|(\.))*$', line_up_to_and_including_word)
		if not match:
			return None

		matched_string = match.group(0)
		region = sublime.Region(word.b - len(matched_string), word.b)
		return (matched_string, region)

	def did_start_debugging(self, session: Session): ...

	def did_stop_debugging(self, session: Session): ...

	async def on_custom_event(self, session: Session, event: str, body: Any):
		core.info(f'event not handled `{event}`')

	async def on_custom_request(self, session: Session, command: str, arguments: dict[str, Any]) -> dict[str, Any] | None: ...

	def on_saved_source_file(self, session: Session, file: str): ...

	def ui(self, debugger: Debugger) -> Any | None: ...

	async def on_navigate_to_source(self, source: dap.SourceLocation) -> tuple[str, str, list[tuple[str, Any]]] | None:
		"""
		Allows the adapter to supply content when navigating to source.
		Returns: None to keep the default behavior, else a tuple (content, mime_type, custom_view_settings)
		"""
		return None
