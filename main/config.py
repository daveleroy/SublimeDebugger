
from .breakpoints import Breakpoints, Breakpoint
from .configurations import Configuration
from sublime_db.core.typecheck import (
	Optional,
	List
)

import sublime
import os
import json

FILE_LOG = 'debug.log'
FILE_BREAKPOINTS = 'breakpoints_data.json'
FILE_SETTINGS = 'debug.sublime-settings'
FILE_PERSISTANCE = 'persistance.json'


def package_path(path: str) -> str:
	return "{}/sublime_db/{}".format(sublime.packages_path(), path)


class PersistedData:
	def __init__(self, project_name: str) -> None:
		self.data = _persisted_for_project(project_name)

	def save_breakpoints(self, breakpoints: Breakpoints) -> None:
		json_breakpoints = []
		for bp in breakpoints.breakpoints:
			json_breakpoints.append(bp.into_json())
		self.data['breakpoints'] = json_breakpoints

	def load_breakpoints(self) -> List[Breakpoint]:
		breakpoints = []
		for breakpoint_json in self.data.get('breakpoints', []):
			breakpoints.append(Breakpoint.from_json(breakpoint_json))
		return breakpoints

	def save_configuration_option(self, configuration: Configuration) -> None:
		self.data['config_name'] = configuration.name
		self.data['config_maybe_at_index'] = configuration.index

	def load_configuration_option(self, configurations: List[Configuration]) -> Optional[Configuration]:
		config_name = self.data.get('config_name')
		config_maybe_at_index = self.data.get('config_maybe_at_index')

		if config_name is None or config_maybe_at_index is None:
			return None

		try:
			configuration = configurations[config_maybe_at_index]
			if configuration.name == config_name:
				return configuration
		except IndexError:
			pass

		for configuration in configurations:
			if configuration.name == config_name:
				return configuration

		return None

	def save_to_file(self) -> None:
		_save_all_data()


_all_data = None #type: Optional[dict]


def _save_all_data() -> None:
	assert not _all_data is None
	data = json.dumps(_all_data)
	file = open(package_path(FILE_PERSISTANCE), 'w+')
	contents = file.write(data)
	file.close()


def _persisted_for_project(project_name: str) -> dict:
	global _all_data
	try:
		file = open(package_path(FILE_PERSISTANCE), 'r+')
		contents = file.read()
		file.close()
		_all_data = json.loads(contents)
	except FileNotFoundError:
		_all_data = {}
	assert not _all_data is None
	project_data = _all_data.setdefault(project_name, {})
	return project_data
