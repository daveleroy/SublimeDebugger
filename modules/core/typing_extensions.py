from typing import Any, TypeVar, Generic

try:
	from typing_extensions import Unpack, TypeVarTuple, ParamSpec, TypeAlias, Concatenate

except ImportError as e:

	class _GetAttr(type):
		def __getitem__(self, x: Any):
			return self

	class _Generic(metaclass=_GetAttr):
		pass

	# just add these in so things compile if needed
	globals()['TypeVarTuple'] = TypeVar
	globals()['ParamSpec'] = TypeVar
	globals()['TypeAlias'] = TypeVar

	globals()['Concatenate'] = _Generic
	globals()['Unpack'] = _Generic
	globals()['Generic'] = _Generic
