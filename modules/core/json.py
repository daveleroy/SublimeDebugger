from __future__ import annotations
import os
from typing import Any, BinaryIO, TextIO, Callable, Mapping, TypeVar

import json
import dataclasses
import hashlib

from .util import debugger_storage_path, write
from .typing_extensions import TypeAlias


K = TypeVar("K") #  key type
T = TypeVar("T") #  value type


def json_decode(contents: str|bytes) -> JSON:
	return json.loads(contents, object_hook=object_hook)

def json_decode_b(contents: BinaryIO|TextIO) -> JSON:
	return json.load(contents, object_hook=object_hook)

def json_decode_file(path: str) -> JSON:
	with open(path, encoding='utf8') as file:
		return json_decode_b(file)

def json_encode(obj: Any, pretty=False):
	if pretty:
		return json.dumps(obj, cls=JSONEncoder, indent='\t')
	return json.dumps(obj, cls=JSONEncoder)

class DottedDict(dict, Mapping[K, T]):
	__getitem__ = dict.get
	__getattr__:Callable[[str], Any] = dict.get #type: ignore
	__setattr__ = dict.__setitem__ #type: ignore
	__delattr__ = dict.__delitem__ #type: ignore

def object_hook(object: dict[Any, Any]):
	return DottedDict(object)

class JSONEncoder(json.JSONEncoder):
	def default(self, o: Any):
		if dataclasses.is_dataclass(o):
			# note: this removes None values from dataclasses when converting them to json.
			# In cases where we want to keep null values we will need to figure something else out
			return dataclasses.asdict(o, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})

		return super().default(o)

class JSON(DottedDict[str, 'JSON_VALUE']):
	...

JSON_VALUE: TypeAlias = 'DottedDict[str, "JSON_VALUE"] | list[JSON_VALUE] | str | int | float | bool | None'

VERSION_NUMBER = 0

def _file_from_key(key: str):
	name = os.path.basename(key).split('.')[0]
	return f'{debugger_storage_path()}/{name}({hashlib.md5(key.encode()).hexdigest()[:10]}).json'

def load_json_from_package_data(key: str) -> JSON:
	path = _file_from_key(key)

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
	path = _file_from_key(key)
	json['_version'] = VERSION_NUMBER
	debugger_storage_path(ensure_exists=True)
	write(path, json_encode(json, pretty=True), overwrite_existing=True)
