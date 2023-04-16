from __future__ import annotations
from typing import Any, BinaryIO, Callable, Mapping, TypeVar

import json
import dataclasses

from .util import package_path, make_directory, write

from .typing_extensions import TypeAlias


K = TypeVar("K") #  key type
T = TypeVar("T") #  value type


def json_decode(contents: str|bytes) -> JSON:
	return json.loads(contents, object_hook=object_hook)

def json_decode_b(contents: BinaryIO) -> JSON:
	return json.load(contents, object_hook=object_hook)

def json_encode(obj: Any, pretty=False):
	if pretty:
		return json.dumps(obj, cls=JSONEncoder, indent='\t')
	return json.dumps(obj, cls=JSONEncoder)

class DottedDict(dict, Mapping[K, T]):
	__getitem__ = dict.get
	__getattr__:Callable[[self, str], Any] = dict.get #type: ignore
	__setattr__ = dict.__setitem__ #type: ignore
	__delattr__ = dict.__delitem__ #type: ignore

def object_hook(object: dict[Any, Any]):
	return DottedDict(object)

class JSONEncoder(json.JSONEncoder):
	def default(self, o: Any):
		if dataclasses.is_dataclass(o):
			return dataclasses.asdict(o)
		return super().default(o)

JSON: TypeAlias = DottedDict[str, 'JSON_VALUE']
JSON_VALUE: TypeAlias = 'DottedDict[str, "JSON_VALUE"] | list[JSON_VALUE] | str | int | float | bool | None'

VERSION_NUMBER = 0

def load_json_from_package_data(key: str) -> JSON:
	key = ''.join(x for x in key if x.isalnum())
	key = key[-128:]

	path = f'{package_path()}/data/{key}.json'

	try:
		with open(path, 'r') as file:
			contents = file.read() or "{}"

		json = json_decode(contents)
		if json.get("_version") == VERSION_NUMBER:
			return json

	except FileNotFoundError:
		pass

	return JSON()

def save_json_to_package_data(key: str, json: Any):
	key = ''.join(x for x in key if x.isalnum())
	key = key[-128:]

	json['_version'] = VERSION_NUMBER
	make_directory(f'{package_path()}/data')
	write(f'{package_path()}/data/{key}.json', json_encode(json, pretty=True), overwrite_existing=True)
