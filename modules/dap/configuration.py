from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict

from ..import core
from ..import dap
from .transport import Transport

import sublime
import re

if TYPE_CHECKING:
	from .session import Session
	from .debugger import Debugger

class AdapterInstaller:
	async def install(self, version: str|None, log: core.Logger) -> None: ...
	async def uninstall(self) -> None: ...

	def install_path(self) -> str: ...

	def installed_version(self) -> str|None: 
		return '1.0.0'

	async def installable_versions(self, log: core.Logger) -> list[str]: 
		return []

	def configuration_snippets(self) -> list[dict[str, Any]] | None: ...
	def configuration_schema(self) -> dict[str, Any] | None: ...


class AdapterConfiguration:
	type: str
	types: list[str] = []
	
	docs: str | None
	development: bool = False
	internal: bool = False

	installer = AdapterInstaller()

	async def start(self, log: core.Logger, configuration: ConfigurationExpanded) -> Transport: ...

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

	def commands(self) -> list[Any]:
		return []

	def settings(self, debugger: Debugger) -> list[Any]:
		return []

	def ui(self, debugger: Debugger) -> Any|None:
		...

	async def on_navigate_to_source(self, source: dap.SourceLocation) -> tuple[str, str, list[tuple[str, Any]]]|None:
		"""
		Allows the adapter to supply content when navigating to source.
		Returns: None to keep the default behavior, else a tuple (content, mime_type, custom_view_settings)
		"""
		return None


class Configuration(Dict[str, Any]):
	def __init__(self, name: str, index: int, type: str, request: str, all: dict[str, Any]):
		super().__init__(all)

		self.name = name
		self.id_ish = f'configuration_{name}_{index}'
		self.type = type
		self.request = request

	@staticmethod
	def from_json(json: dict[str, Any], index: int) -> 'Configuration':
		name = json.get('name')
		assert name, 'expecting name for debug.configuration'
		type = json.get('type')
		assert type, 'expecting type for debug.configuration'
		request = json.get('request')
		assert request, 'expecting request for debug.configuration'
		return Configuration(name, index, type, request, json)


class ConfigurationExpanded(Configuration):
	def __init__(self, configuration: Configuration, variables: Any):
		all = _expand_variables_and_platform(configuration, variables)
		super().__init__(configuration.name, -1, configuration.type, configuration.request, all)

		self.variables = variables
		self.pre_debug_task: TaskExpanded|None = None
		self.post_debug_task: TaskExpanded|None = None


class ConfigurationCompound:
	def __init__(self, name: str, index: int, configurations: list[str]) -> None:
		self.name = name
		self.id_ish = f'compound_{name}_{index}'
		self.configurations = configurations

	@staticmethod
	def from_json(json: dict[str, Any], index: int) -> 'ConfigurationCompound':
		name = json.get('name')
		assert name, 'expecting name for debug.compound'
		configurations = json.get('configurations')
		assert configurations, 'expecting configurations for debug.compound'
		return ConfigurationCompound(name, index, configurations)


class Task (Dict[str, Any]):
	def __init__(self, arguments: dict[str, Any]) -> None:
		super().__init__(arguments)
		self.name = arguments.get('name', 'Untitled')

	@staticmethod
	def from_json(json: dict[str, Any]):
		return Task(json)


class TaskExpanded(Task):
	def __init__(self, task: Task, variables: dict[str, str]) -> None:
		arguments = _expand_variables_and_platform(task, variables)
		# if we don't remove these additional arguments Default.exec.ExecCommand will be unhappy		
		super().__init__(arguments)

		cmd: str|list[str]|None = arguments.get('cmd')

		if 'name' in arguments:
			name = arguments['name']
		elif isinstance(cmd, str):
			name = cmd
		elif isinstance(cmd, list) and cmd:
			name = cmd[0]
		else:
			name = 'Untitled'

		background = arguments.get('background', False)

		self.name: str = name
		self.background = background

		if 'name' in self:
			del self['name']
		if 'background' in self:
			del self['background']

		if '$' in self:
			del self['$']
	

	



def _expand_variables_and_platform(json: dict[str, Any], variables: dict[str, str] | None):
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
		json = sublime.expand_variables(json, json_variables)
		del json['$']

	if variables := variables:
		json = sublime.expand_variables(json, variables)

	return json
