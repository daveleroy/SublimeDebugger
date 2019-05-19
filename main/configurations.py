from sublime_db.core.typecheck import List, Optional, Generator, Any, Callable, Dict

import sublime
import json
import re
from sublime_db import core
from .adapter_configuration import AdapterConfiguration
from .util import get_setting


class Configuration:
	def __init__(self, name: str, type: str, request: str, all: dict) -> None:
		self.name = name
		self.type = type
		self.all = all
		self.index = -1
		self.request = request

	@staticmethod
	def from_json(json: dict) -> 'Configuration':
		name = json.get('name')
		assert name, 'expecting name for debug.configuration'
		type = json.get('type')
		assert type, 'expecting type for debug.configuration'
		request = json.get('request')
		assert request, 'expecting request for debug.configuration'
		return Configuration(name, type, request, json)


