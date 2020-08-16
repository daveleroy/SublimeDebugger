from .. typecheck import *
from .. import core

from .adapter import Configuration, ConfigurationCompound
from .breakpoints import Breakpoints

import os
import json

def _project_data_file(project_path: str) -> str:
	import hashlib
	hash = hashlib.sha224(project_path.encode('utf-8')).hexdigest()
	return os.path.join(core.current_package(), "data/{}.json".format(hash))


class PersistedData:
	def __init__(self, project_name: str) -> None:
		self.file_name = _project_data_file(project_name)
		self.json = {} #type: dict
		VERSION_NUMBER = 0
		self.json["version"] = VERSION_NUMBER

		try:
			file = open(self.file_name, 'r+')
			contents = file.read()
			file.close()
			j = json.loads(contents)
			if j["version"] == VERSION_NUMBER:
				self.json = j
		except FileNotFoundError:
			pass

	def save_breakpoints(self, breakpoints: Breakpoints) -> None:
		self.json['breakpoints'] = breakpoints.into_json()

	def load_breakpoints(self, breakpoints: Breakpoints):
		breakpoints.load_from_json(self.json.get('breakpoints', {}))

	def save_configuration_option(self, configuration: Union[Configuration, ConfigurationCompound]) -> None:
		self.json['config_name'] = configuration.name
		self.json['config_id_ish'] = configuration.id_ish

	def load_configuration_option(self, configurations: List[Configuration], compounds: List[ConfigurationCompound]) -> Optional[Union[Configuration, ConfigurationCompound]]:
		config_name = self.json.get('config_name')
		config_id_ish = self.json.get('config_id_ish')

		if config_name is None or config_id_ish is None:
			return None

		for compound in compounds:
			if compound.id_ish == config_id_ish:
				return compound
		for configuration in configurations:
			if configuration.id_ish == config_id_ish:
				return configuration

		for compound in compounds:
			if compound.name == config_name:
				return compound
		for configuration in configurations:
			if configuration.name == config_name:
				return configuration

		return None

	def save_to_file(self) -> None:
		
		data = json.dumps(self.json, indent='\t', sort_keys=True)
		file = open(self.file_name, 'w+')
		contents = file.write(data)
		file.close()


