
from .breakpoints import Breakpoints, Breakpoint
from .configurations import Configuration
from sublime_db.core.typecheck import (
	Optional,
	List
)
from sublime_db import core

import sublime
import os
import json

def _project_data_file(project_path: str) -> str:
	import hashlib
	hash = hashlib.sha224(project_path.encode('utf-8')).hexdigest()
	return os.path.join(sublime.packages_path(), "sublime_db/data/{}.json".format(hash))


class PersistedData:
	def __init__(self, project_name: str) -> None:
		self.project_name = project_name
		self.data = {}
		VERSION_NUMBER = 0
		self.data["version"] = VERSION_NUMBER

		try:
			file_name = _project_data_file(project_name)
			file = open(file_name, 'r+')
			contents = file.read()
			file.close()
			data = json.loads(contents)
			if data["version"] == VERSION_NUMBER:
				self.data = data
		except FileNotFoundError:
			pass

	def save_breakpoints(self, breakpoints: Breakpoints) -> None:
		self.data['breakpoints'] = breakpoints.into_json()

	def load_breakpoints(self, breakpoints: Breakpoints):
		breakpoints.load_from_json(self.data.get('breakpoints', {}))

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
		file_name = _project_data_file(self.project_name)
		data = json.dumps(self.data)
		file = open(file_name, 'w+')
		contents = file.write(data)
		file.close()


