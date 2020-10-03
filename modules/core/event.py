from ..typecheck import *

T = TypeVar('T')

class Handle (Generic[T]):
	def __init__(self, event: 'Event[T]', callback: Callable[[T], Any]) -> None:
		self.callback = callback
		self.event = event

	def dispose(self) -> None:
		self.event.handlers.remove(self)


class Event (Generic[T]):
	def __init__(self) -> None:
		self.handlers = [] # type: List[Handle[T]]

	@overload
	def add(self: 'Event[None]', callback: Callable[[], Any]) -> Handle[None]:
		...

	@overload
	def add(self, callback: Callable[[T], Any]) -> Handle[T]:
		...

	def add(self, callback: Callable[[T], Any]) -> Handle[T]: #type: ignore
		handle = Handle(self, callback)
		self.handlers.append(handle)
		return handle

	def add_handle(self, handle: Handle[T]) -> None:
		self.handlers.append(handle)

	def __call__(self, *data: T) -> bool:
		return self.post(*data)

	def __bool__(self) -> bool:
		return bool(self.handlers)

	def post(self, *data: T) -> bool:
		r = False
		for h in self.handlers:
			r = r or h.callback(*data)
		return bool(r)
