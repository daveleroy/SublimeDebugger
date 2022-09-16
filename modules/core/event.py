from __future__ import annotations
from ..typecheck import *

T = TypeVar('T')
Args = TypeVarTuple('Args')

class Handle:
	def __init__(self, event: Any, callback: Any) -> None:
		self.callback = callback
		self.event = event

	def dispose(self) -> None:
		try:
			self.event.handlers.remove(self)
		except ValueError:
			...


class Event (Generic[Unpack[Args]]):
	def __init__(self) -> None:
		self.handlers: list[Handle] = []

	@overload
	def add(self, callback: Callable[[], Any]) -> Handle: ...

	@overload
	def add(self, callback: Callable[[Unpack[Args]], Any]) -> Handle: ...

	def add(self, callback: Any) -> Handle:
		handle = Handle(self, callback)
		self.handlers.append(handle)
		return handle

	def add_handle(self, handle: Handle) -> None:
		self.handlers.append(handle)

	def __call__(self, *data: Unpack[Args]) -> bool:
		r = False
		for h in self.handlers:
			r = r or h.callback(*data)
		return bool(r)
		return self.post(*data) #type: ignore

	def post(self) -> bool:
		return self() #type: ignore

	def __bool__(self) -> bool:
		return bool(self.handlers)


class EventReturning (Generic[T, Unpack[Args]]):
	def __init__(self) -> None:
		self.handlers: list[Handle] = []

	@overload
	def add(self, callback: Callable[[], Any]) -> Handle: ...

	@overload
	def add(self, callback: Callable[[Unpack[Args]], T|None]) -> Handle: ...

	def add(self, callback: Any) -> Handle:
		handle = Handle(self, callback)
		self.handlers.append(handle)
		return handle

	def add_handle(self, handle: Handle) -> None:
		self.handlers.append(handle)

	def __call__(self, *data: Unpack[Args]) -> T:
		return self.post(*data) #type: ignore

	def __bool__(self) -> bool:
		return bool(self.handlers)

	def post(self, *data: Unpack[Args]) -> T|None:
		r = None
		for h in self.handlers:
			r = r or h.callback(*data)
		return r