from __future__ import annotations

from ...typecheck import *
from ...import core

import sublime


class Transport(Protocol):
	def write(self, message: bytes) -> None:
		...
	def readline(self) -> bytes:
		...
	def read(self, n: int) -> bytes:
		...
	def dispose(self) ->None:
		...

class AdapterConfiguration (Protocol):
	@property
	def type(self) -> str: ...

	async def start(self, log: core.Logger, configuration: ConfigurationExpanded) -> Transport: ...

	@property
	def installed_version(self) -> Optional[str]: ...

	@property
	def configuration_snippets(self) -> Optional[list]: ...

	@property
	def configuration_schema(self) -> Optional[dict]: ...

	async def configuration_resolve(self, configuration: ConfigurationExpanded) -> ConfigurationExpanded:
		return configuration

	async def install(self, log: core.Logger): ...

	def on_hover_provider(self, view: sublime.View, point: int) -> Optional[Tuple[str, sublime.Region]]:
		word = view.word(point)
		word_string = word and view.substr(word)
		if word_string:
			return (word_string, word)
		return None

	def did_start_debugging(self, session):
		...

	def did_stop_debugging(self, session):
		...

	def on_custom_event(self, session):
		...

	async def on_custom_request(self, session):
		...

	def commands(self):
		return []

	def settings(self, sessions):
		return []

class Configuration(dict):
	def __init__(self, name: str, index: int, type: str, request: str, all: dict) -> None:
		super().__init__(all)

		self.name = name
		self.id_ish = f'configuration_{name}_{index}'
		self.type = type
		self.request = request

	@staticmethod
	def from_json(json: dict, index: int) -> 'Configuration':
		name = json.get('name')
		assert name, 'expecting name for debug.configuration'
		type = json.get('type')
		assert type, 'expecting type for debug.configuration'
		request = json.get('request')
		assert request, 'expecting request for debug.configuration'
		return Configuration(name, index, type, request, json)


class ConfigurationExpanded(Configuration):
	def __init__(self, configuration: Configuration, variables: Any) -> None:
		all = ConfigurationExpanded._expand_variables_and_platform(configuration, variables)
		super().__init__(configuration.name, -1, configuration.type, configuration.request, all)

		self.pre_debug_task: Optional[TaskExpanded] = None
		self.post_debug_task: Optional[TaskExpanded] = None

	@staticmethod
	def _expand_variables_and_platform(json: dict, variables: Optional[dict]) -> dict:
		json = json.copy()

		platform: Optional[dict] = None
		if core.platform.osx:
			platform = json.get('osx')
		elif core.platform.linux:
			platform = json.get('linux')
		elif core.platform.windows:
			platform = json.get('windows')

		if platform:
			for key, value in platform.items():
				json[key] = value

		if variables is not None:
			return sublime.expand_variables(json, variables)

		return json


class ConfigurationCompound:
	def __init__(self, name: str, index: int, configurations: List[str]) -> None:
		self.name = name
		self.id_ish = f'compound_{name}_{index}'
		self.configurations = configurations

	@staticmethod
	def from_json(json: dict, index: int) -> 'ConfigurationCompound':
		name = json.get('name')
		assert name, 'expecting name for debug.compound'
		configurations = json.get('configurations')
		assert configurations, 'expecting configurations for debug.compound'
		return ConfigurationCompound(name, index, configurations)


class Task (dict):
	def __init__(self, arguments: dict) -> None:
		super().__init__(arguments)
		self.name = self.get('name', 'Untitled')

	@staticmethod
	def from_json(json):
		return Task(json)


class TaskExpanded(Task):
	def __init__(self, task: Task, variables: Any) -> None:
		all = ConfigurationExpanded._expand_variables_and_platform(task, variables)
		super().__init__(all)
