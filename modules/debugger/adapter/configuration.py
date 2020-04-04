from ...typecheck import *
from ...import core
import sublime

def _expand_variables_and_platform(json: dict, variables: Optional[dict]) -> dict:
	platform = None #type: Optional[dict]
	if core.platform.osx:
		platform = json.get('osx')
	elif core.platform.linux:
		platform = json.get('linux')
	elif core.platform.windows:
		platform = json.get('windows')

	if platform:
		json = json.copy()
		for key, value in platform.items():
			json[key] = value

	if variables is not None:
		return sublime.expand_variables(json, variables)

	return json


class Configuration:
	def __init__(self, name: str, index: int, type: str, request: str, all: dict) -> None:
		self.name = name
		self.id_ish = f'configuration_{name}_{index}'
		self.type = type
		self.request = request
		self.all = all

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
		all = _expand_variables_and_platform(configuration.all, variables)
		super().__init__(configuration.name, -1, configuration.type, configuration.request, all)
		self.verify()

	def verify(self):
		def warn(text: str):
			sublime.error_message(text)

		def error(text: str):
			raise core.Error(text)

		if self.type == "python":
			if self.request == "launch":
				if not self.all.get("program"):
					warn("Warning: Check your debugger configuration.\n\nField `program` in configuration is empty. If it contained a $variable that variable may not have existed.""")
			return

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