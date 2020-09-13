from .. typecheck import *
from .. import core

import os
import sublime

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
			file = open(self.file_name, 'r')
			contents = file.read()
			file.close()
			j = sublime.decode_value(contents) or {}
			if j.get("version") == VERSION_NUMBER:
				self.json = j
		except FileNotFoundError:
			pass

	def save_to_file(self) -> None:
		data = sublime.encode_value(self.json, True)
		file = open(self.file_name, 'w')
		file.write(data)
		file.close()


