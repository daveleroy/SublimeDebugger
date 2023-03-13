from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict

from ..import core
from ..import dap

from .transport import Transport, TransportProtocol

import sublime
import re
import os

if TYPE_CHECKING:
	from .session import Session
	from .debugger import Debugger
	from .variable import SourceLocation


class AdapterInstaller:
	type: str

	async def perform_install(self, version: str, log: core.Logger):
		self.remove()
		core.make_directory(self.data_path())
		core.make_directory(self.temporary_install_path())

		await self.install(version, log)


		os.rename(self.temporary_install_path(), self.install_path())

	async def install(self, version: str, log: core.Logger) -> None: ...

	def remove(self) -> None:
		core.remove_file_or_dir(self.temporary_install_path())
		core.remove_file_or_dir(self.install_path())

	def temporary_install_path(self) -> str:
		return f'{core.package_path()}/data/{self.type}.tmp'

	def install_path(self) -> str:
		return f'{core.package_path()}/data/{self.type}'

	def data_path(self) -> str:
		return f'{core.package_path()}/data'

	def installed_version(self) -> str|None:
		return '1.0.0'

	async def installable_versions(self, log: core.Logger) -> list[str]:
		return []

	def configuration_snippets(self, schema_type: str|None = None) -> list[dict[str, Any]] | None: ...
	def configuration_schema(self, schema_type: str|None = None) -> dict[str, Any] | None: ...


class AdapterConfiguration:
	type: str
	types: list[str] = []

	docs: str | None
	development: bool = False
	internal: bool = False

	installer = AdapterInstaller()

	async def start(self, log: core.Logger, configuration: ConfigurationExpanded) -> Transport|TransportProtocol: ...

	@property
	def installed_version(self) -> str | None:
		return self.installer.installed_version()

	@property
	def configuration_snippets(self) -> list[dict[str, Any]] | None:
		return self.installer.configuration_snippets()

	@property
	def configuration_schema(self) -> dict[str, Any] | None:
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

	def ui(self, debugger: Debugger) -> Any|None:
		...

	async def on_navigate_to_source(self, source: dap.SourceLocation) -> tuple[str, str, list[tuple[str, Any]]]|None:
		"""
		Allows the adapter to supply content when navigating to source.
		Returns: None to keep the default behavior, else a tuple (content, mime_type, custom_view_settings)
		"""
		return None


class Configuration(Dict[str, Any]):
	def __init__(self, name: str, index: int, type: str, request: str, all: dict[str, Any], source: SourceLocation|None = None):
		super().__init__(all)

		self.name = name
		self.id_ish = f'configuration_{name}_{index}'
		self.type = type
		self.request = request
		self.source = source

	@staticmethod
	def from_json(json: dict[str, Any], index: int, source: SourceLocation|None = None) -> Configuration:
		return Configuration(json['name'], index, json['type'], json['request'], json, source)


class ConfigurationExpanded(Configuration):
	def __init__(self, configuration: Configuration, variables: Any):
		all = _expand_variables_and_platform(configuration, variables)
		super().__init__(configuration.name, -1, configuration.type, configuration.request, all, configuration.source)

		self.variables = variables
		self.pre_debug_task: TaskExpanded|None = None
		self.post_debug_task: TaskExpanded|None = None


class ConfigurationCompound:
	def __init__(self, name: str, index: int, configurations: list[str], source: SourceLocation|None = None) -> None:
		self.name = name
		self.id_ish = f'compound_{name}_{index}'
		self.configurations = configurations
		self.source = source

	@staticmethod
	def from_json(json: dict[str, Any], index: int, source: SourceLocation|None = None) -> ConfigurationCompound:
		return ConfigurationCompound(json['name'], index, json['configurations'], source)


class Task (Dict[str, Any]):
	def __init__(self, arguments: dict[str, Any], source: SourceLocation|None = None) -> None:
		super().__init__(arguments)
		self.name = arguments['name']
		self.source = source

	@staticmethod
	def from_json(json: dict[str, Any], source: SourceLocation|None = None):
		return Task(json, source)


class TaskExpanded(Task):
	def __init__(self, task: Task, variables: dict[str, str]) -> None:
		arguments = _expand_variables_and_platform(task, variables)
		# if we don't remove these additional arguments Default.exec.ExecCommand will be unhappy
		super().__init__(arguments, task.source)



		cmd: str|list[str]|None = arguments.get('cmd')

		if 'name' in arguments:
			name = arguments['name']
		elif isinstance(cmd, str):
			name = cmd
		elif isinstance(cmd, list) and cmd:
			name = cmd[0]
		else:
			name = 'Untitled'

		self.variables = variables
		self.name: str = name
		self.background: bool = arguments.get('background', False)
		self.start_file_regex: str|None = arguments.get('start_file_regex')
		self.end_file_regex: str|None = arguments.get('end_file_regex')

		for key in ['name', 'background', 'start_file_regex', 'end_file_regex', '$']:
			if key in self:
				del self[key]


def _expand_variables(json: Any, variables: dict[str, str], supress_errors: bool = False):
	if type(json) is str:
		regex = re.compile('(\${(.*)})')
		for match, key in regex.findall(json):
			if value := variables.get(key):
				json = json.replace(match, value)
			elif not supress_errors:
				error = f'Unable to expand variable ${{{key}}}, available variables\n\n'
				for variable in variables:
					error += f'${{{variable}}}\n'

				raise core.Error(error)

		return json

	if type(json) is dict:
		for key in json.keys():
			json[key] = _expand_variables(json[key], variables, supress_errors)

	if type(json) is list:
		for i in range(0, len(json)):
			json[i] = _expand_variables(json[i], variables, supress_errors)

	return json

def _expand_variables_and_platform(json: dict[str, Any], variables: dict[str, str]):
	json = json.copy()

	platform = None
	if core.platform.osx:
		platform = json.get('osx')
	elif core.platform.linux:
		platform = json.get('linux')
	elif core.platform.windows:
		platform = json.get('windows')

	if platform:
		for key, value in platform.items():
			json[key] = value

	# This allows us to add a list of variables to each configuration which case be use throughout the configuration.
	# Its mostly so we can redefine $project_path when specifying a project file in debugger_configurations so $project_path refers to the correct location
	if json_variables := json.get('$'):
		json = _expand_variables(json, json_variables, supress_errors=True)
		del json['$']

	if variables := variables:
		json = _expand_variables(json, variables)

	return json
