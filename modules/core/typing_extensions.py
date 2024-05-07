from typing import TYPE_CHECKING, Any, TypeVar, Generic

if TYPE_CHECKING:
	from typing_extensions import Unpack, TypeVarTuple, ParamSpec, TypeAlias, Concatenate

else:
	class _GetAttr(type):
			def __getitem__(self, x: Any):
				return self
	class _Generic(metaclass=_GetAttr):
		pass

	# Add these in so things work at runtime
	globals()['TypeVarTuple'] = TypeVar
	globals()['ParamSpec'] = TypeVar
	globals()['TypeAlias'] = TypeVar

	globals()['Concatenate'] = _Generic
	globals()['Unpack'] = _Generic
	globals()['Generic'] = _Generic
