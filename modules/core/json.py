from __future__ import annotations
from typing import Any, BinaryIO, Callable, Mapping, TypeVar

import json
import dataclasses
from .typing import TypeAlias


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
