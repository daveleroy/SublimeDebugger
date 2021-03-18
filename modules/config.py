from __future__ import annotations
from .typecheck import *

from .import core

import os
import sublime
import hashlib


class PersistedData:
	def __init__(self, project_name: str) -> None:
		VERSION_NUMBER = 0

		hash = hashlib.sha224(project_name.encode('utf-8')).hexdigest()
		self.file_name = os.path.join(core.current_package(), "data/{}.json".format(hash))
		self.json = {
			"version": VERSION_NUMBER
		}

		try:
			with open(self.file_name, 'r') as file:
				contents = file.read()

			json = sublime.decode_value(contents) or {}
			if json.get("version") == VERSION_NUMBER:
				self.json = json

		except FileNotFoundError:
			pass

	def save_to_file(self) -> None:
		with open(self.file_name, 'w') as file:
			file.write(sublime.encode_value(self.json, True))


