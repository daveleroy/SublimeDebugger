from __future__ import annotations
from typing import Any
from .import core

VERSION_NUMBER = 0

def load(key: str) -> core.JSON:
	key = ''.join(x for x in key if x.isalnum())
	key = key[-128:]

	path = f'{core.package_path()}/data/{key}.json'

	try:
		with open(path, 'r') as file:
			contents = file.read() or "{}"

		json = core.json_decode(contents)
		if json.get("_version") == VERSION_NUMBER:
			return json

	except FileNotFoundError:
		pass

	return core.JSON()

def save(key: str, data: Any):
	key = ''.join(x for x in key if x.isalnum())
	key = key[-128:]

	data['_version'] = VERSION_NUMBER
	core.make_directory(f'{core.package_path()}/data')
	core.write(f'{core.package_path()}/data/{key}.json', core.json_encode(data, pretty=True), overwrite_existing=True)