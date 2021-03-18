from __future__ import annotations
from ..typecheck import *

T = TypeVar('T')
Args = TypeVarTuple('Args')

class Handle (Generic[T]):
	def __init__(self, event: Event[T], callback: Callable[[T], Any]) -> None:
		self.callback = callback
		self.event = event

	def dispose(self) -> None:
		self.event.handlers.remove(self)


class Event (Generic[Unpack[Args]]):
	def __init__(self) -> None:
		self.handlers: list[Handle[Any]] = []

	@overload
	def add(self, callback: Callable[[], Any]) -> Handle[Any]: ...

	@overload
	def add(self, callback: Callable[[Unpack[Args]], Any]) -> Handle[Any]: ...

	def add(self, callback: Any) -> Handle[Any]:
		handle = Handle(self, callback)
		self.handlers.append(handle)
		return handle

	def add_handle(self, handle: Handle[Any]) -> None:
		self.handlers.append(handle)

	def __call__(self, *data: Unpack[Args]) -> bool:
		return self.post(*data) #type: ignore

	def __bool__(self) -> bool:
		return bool(self.handlers)

	def post(self, *data: Unpack[Args]) -> bool:
		r = False
		for h in self.handlers:
			r = r or h.callback(*data)
		return bool(r)
