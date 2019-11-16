from ...typecheck import *
from ...import core
import sublime

class Configuration:
	def __init__(self, name: str, type: str, request: str, all: dict) -> None:
		self.name = name
		self.type = type
		self.index = -1
		self.request = request
		self.all = all

	@staticmethod
	def from_json(json: dict) -> 'Configuration':
		name = json.get('name')
		assert name, 'expecting name for debug.configuration'
		type = json.get('type')
		assert type, 'expecting type for debug.configuration'
		request = json.get('request')
		assert request, 'expecting request for debug.configuration'
		return Configuration(name, type, request, json)

class ConfigurationExpanded(Configuration):
	def __init__(self, configuration: Configuration, variables: Any) -> None:
		from .adapter import _expand_variables_and_platform
		all = _expand_variables_and_platform(configuration.all, variables)
		super().__init__(configuration.name, configuration.type, configuration.request, all)
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
