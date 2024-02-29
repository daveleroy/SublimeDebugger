from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, cast

from ..import core

import re

if TYPE_CHECKING:
	from .variable import SourceLocation


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
		variables, json = _expand_variables_and_platform(configuration, variables)

		super().__init__(configuration.name, -1, configuration.type, configuration.request, json, configuration.source)

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
		variables, json = _expand_variables_and_platform(task, variables)

		super().__init__(json, task.source)

		cmd: str|list[str]|None = json.get('cmd')

		if 'name' in json:
			name = json['name']
		elif isinstance(cmd, str):
			name = cmd
		elif isinstance(cmd, list) and cmd:
			name = cmd[0]
		else:
			name = 'Untitled'

		self.variables = variables
		self.name: str = name
		self.background: bool = json.get('background', False)
		self.start_file_regex: str|None = json.get('start_file_regex')
		self.end_file_regex: str|None = json.get('end_file_regex')

		self.depends_on = json.get('depends_on')
		self.depends_on_order = json.get('depends_on_sequence')

		# if we don't remove these additional arguments Default.exec.ExecCommand will be unhappy
		for key in ['name', 'background', 'start_file_regex', 'end_file_regex', 'depends_on', 'depends_on_order']:
			if key in self:
				del self[key]


def _expand_variables(json: Any, variables: dict[str, str], supress_errors: bool = False):
	if type(json) is str:
		regex = re.compile(r'(\${([^}]*)})')
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

	# This allows us to add a list of variables to each configuration which case be use throughout the configuration.
	# Its mostly so we can redefine $project_path when specifying a project file in debugger_configurations so $project_path refers to the correct location
	if extra_variables := json.get('$'):
		del json['$']

		variables = variables.copy()
		for key in extra_variables:
			variables[key] = extra_variables[key]

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

	if variables := variables:
		json = cast('dict[str, Any]', _expand_variables(json, variables))

	return variables, json
