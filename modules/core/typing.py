from typing import (
	Any,
	Generic,
	List,
	Dict,
	Tuple,
	Awaitable,
	Iterator,
	Iterable,
	TypeVar,
	Union,
	Protocol,
	overload,
	TYPE_CHECKING,
	Optional,
	Set,
	Sequence,
	Coroutine,
	Callable,
	ClassVar,
	cast,
	Generator,
	Mapping,
)

try:
	from typing_extensions import Unpack, TypeVarTuple
except ImportError as e:

	class _GetAttr(type):
		def __getitem__(self, x: Any):
			return self

	class _Generic(metaclass=_GetAttr):
		pass

	# just add these in so things compile if needed
	globals()['TypeVarTuple'] = TypeVar
	globals()['Unpack'] = _Generic
	globals()['Generic'] = _Generic