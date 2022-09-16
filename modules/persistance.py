from __future__ import annotations
from .typecheck import *

from .import core

import os
import hashlib


VERSION_NUMBER = 0

def file_name_for_project_name(project_name: str):
	hash = hashlib.sha224(project_name.encode('utf-8')).hexdigest()
	file_name = os.path.join(core.current_package(), "data/{}.json".format(hash))
	return file_name
	
def load(project_name: str) -> Any:
	file_name = file_name_for_project_name(project_name)
	try:
		with open(file_name, 'r') as file:
			contents = file.read() or "{}"

		json = core.json_decode(contents)
		if json.get("_version") == VERSION_NUMBER:
			return json

	except FileNotFoundError:
		pass
	return {}

def save(project_name: str, data: Any):
	file_name = file_name_for_project_name(project_name)
	with open(file_name, 'w') as file:
		data['_version'] = VERSION_NUMBER
		data['_project_name'] = project_name
		file.write(core.json_encode(data, pretty=True))



