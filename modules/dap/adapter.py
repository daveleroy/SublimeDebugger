from __future__ import annotations
from typing import TYPE_CHECKING, Any, ClassVar

from .. import core
from .. import dap

from .transport import Transport
from .configuration import ConfigurationExpanded

import sublime
import re
import os

if TYPE_CHECKING:
	from .session import Session
	from .debugger import Debugger


class AdapterInstaller:
	type: str

	async def perform_install(self, version: str, log: core.Logger):
		self.remove()
		core.debugger_storage_path(ensure_exists=True)
		core.make_directory(self.temporary_install_path())

		await self.install(version, log)
		await self.post_install(version, log)

		os.rename(self.temporary_install_path(), self.install_path())

	async def install(self, version: str, log: core.Logger) -> None:
		...

	async def post_install(self, version: str, log: core.Logger) -> None:
		...

	def remove(self) -> None:
		core.remove_file_or_dir(self.temporary_install_path())
		core.remove_file_or_dir(self.install_path())

	def temporary_install_path(self) -> str:
		return os.path.join(core.debugger_storage_path(), f'{self.type}.tmp')

	def install_path(self) -> str:
		return os.path.join(core.debugger_storage_path(), f'{self.type}')

	def installed_version(self) -> str | None:
		return '1.0.0'

	# note versions that include '(' are not installed unless explicity selected from the installable versions menu
	# this supports tags like (prerelease) / (draft)
	async def installable_versions(self, log: core.Logger) -> list[str]:
		return []

	async def installable_versions_with_default(self, log: core.Logger) -> tuple[str, list[str]]:
		versions = await self.installable_versions(log)
		if not versions:
			raise core.Error('No installable versions')

		versions_without_tags = filter(lambda v: not '(' in v, versions)
		version = next(versions_without_tags) or versions[0]
		return version, versions

	def configuration_snippets(self, schema_type: str | None = None) -> list[dict[str, Any]]:
		return []

	def configuration_schema(self, schema_type: str | None = None) -> dict[str, Any]:
		return {}


class AdapterConfigurationRegistery(type):
	def __new__(cls, name, bases, dct):
		kclass = type.__new__(cls, name, bases, dct)
		if bases:
			AdapterConfigurationRegistery.register(kclass())

		return kclass

	registered: ClassVar[list[AdapterConfiguration]] = []
	registered_types: ClassVar[dict[str, AdapterConfiguration]] = {}

	@staticmethod
	def register(adapter: AdapterConfiguration):
		if not adapter.type:
			return

		AdapterConfiguration.registered.append(adapter)
		for type in adapter.types:
			AdapterConfiguration.registered_types[type] = adapter

	@staticmethod
	def get(type: str) -> dap.AdapterConfiguration:
		if adapter := AdapterConfiguration.registered_types.get(type):
			return adapter

		raise core.Error(f'Unable to find debug adapter with the type name "{type}"')

	@staticmethod
	@core.run
	async def install_adapter(console: dap.Console, adapter: dap.AdapterConfiguration, version: str | None) -> None:
		console.log('group-start', f'{core.platform.unicode_unchecked_sigil} Installing {adapter.name}')

		try:
			if version is None:
				version, _ = await adapter.installer.installable_versions_with_default(console)

			await adapter.installer.perform_install(version, console)

		except Exception as error:
			console.log('group-end', None)
			console.error(f'{core.platform.unicode_checked_sigil} Failed: {error}')
			raise error

		from .schema import generate_lsp_json_schema

		generate_lsp_json_schema()

		console.log('success', f'Successfully installed {adapter.name}. Checkout the documentation for this adapter {adapter.docs}')
		console.log('group-end', f'{core.platform.unicode_checked_sigil} Finished')


class AdapterConfiguration(metaclass=AdapterConfigurationRegistery):
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

	async def start(self, log: core.Logger, configuration: ConfigurationExpanded) -> Transport:
		...

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

	def did_start_debugging(self, session: Session):
		...

	def did_stop_debugging(self, session: Session):
		...

	async def on_custom_event(self, session: Session, event: str, body: Any):
		core.info(f'event not handled `{event}`')

	async def on_custom_request(self, session: Session, command: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
		...

	def on_saved_source_file(self, session: Session, file: str):
		...

	def ui(self, debugger: Debugger) -> Any | None:
		...

	async def on_navigate_to_source(self, source: dap.SourceLocation) -> tuple[str, str, list[tuple[str, Any]]] | None:
		"""
		Allows the adapter to supply content when navigating to source.
		Returns: None to keep the default behavior, else a tuple (content, mime_type, custom_view_settings)
		"""
		return None
