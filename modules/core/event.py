from __future__ import annotations
from typing import Any, Callable, overload
from .typing_extensions import TypeVar, TypeVarTuple, ParamSpec, Generic

T = TypeVar('T')
P = ParamSpec('P',)

class Handle:
	def __init__(self, event: Any, callback: Any) -> None:
		self.callback = callback
		self.event = event

	def dispose(self) -> None:
		try: self.event.handles.remove(self)
		except ValueError: ...

class Event (Generic[P]):
	def __init__(self) -> None:
		self.handles: list[Handle] = []

	@overload
	def add(self: Event[None], callback: Callable[[], Any]) -> Handle: ... #type: ignore

	@overload
	def add(self, callback: Callable[P, Any]) -> Handle: ... #type: ignore
	def add(self, callback: Callable[P, Any]) -> Handle: #type: ignore
		handle = Handle(self, callback)
		self.handles.append(handle)
		return handle

	@overload
	def __call__(self: Event[None]) -> bool: ... #type: ignore
	@overload
	def __call__(self, *args: P.args, **kwargs: P.kwargs) -> bool: ... #type: ignore

	def __call__(self, *args: P.args, **kwargs: P.kwargs) -> bool: #type: ignore
		r = False
		for h in self.handles:
			r = r or h.callback(*args, **kwargs)

		return bool(r)


class EventReturning (Generic[P, T]):
	def __init__(self) -> None:
		self.handles: list[Handle] = []

	@overload
	def add(self: Event[None], callback: Callable[[], Any]) -> Handle: ... #type: ignore
	def add(self, callback: Callable[P, Any]) -> Handle: #type: ignore
		handle = Handle(self, callback)
		self.handles.append(handle)
		return handle

	@overload
	def __call__(self: Event[None]) -> T|None: ... #type: ignore
	def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T|None: #type: ignore
		r = None
		for h in self.handles:
			r = r or h.callback(*args, **kwargs)
		return r
