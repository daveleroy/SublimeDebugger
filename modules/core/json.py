from __future__ import annotations
from typing import Any

import json
import dataclasses

def json_decode(contents: str|bytes) -> DottedDict:
	return json.loads(contents, object_hook=object_hook)

def json_encode(obj: Any, pretty=False):
	if pretty:
		return json.dumps(obj, cls=JSONEncoder, indent='\t')
	return json.dumps(obj, cls=JSONEncoder)

class DottedDict(dict): #type: ignore
	__getitem__ = dict.get #type: ignore
	__getattr__ = dict.get #type: ignore
	__setattr__ = dict.__setitem__ #type: ignore
	__delattr__ = dict.__delitem__ #type: ignore

def object_hook(object: dict[Any, Any]):
	return DottedDict(object)

class JSONEncoder(json.JSONEncoder):
	def default(self, o: Any):
		if dataclasses.is_dataclass(o):
			return dataclasses.asdict(o)
		return super().default(o)
