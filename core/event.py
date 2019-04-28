from sublime_db.core.typecheck import (
	Any,
	Generator,
	Callable,
	List,
	Optional,
	TypeVar,
	Generic,
	Union
)

from .core import call_soon_threadsafe

T = TypeVar('T')


class Handle (Generic[T]):
	def __init__(self, event: 'Event[T]', callback: Callable[[T], None]) -> None:
		self.callback = callback
		self.event = event

	def dispose(self) -> None:
		self.event.handlers.remove(self)


class Event (Generic[T]):
	def __init__(self) -> None:
		self.handlers = [] # type: List[Handle[T]]

	def add(self, callback: Callable[[T], None]) -> Handle[T]:
		handle = Handle(self, callback)
		self.handlers.append(handle)
		return handle

	def add_handle(self, handle: Handle[T]) -> None:
		self.handlers.append(handle)

	def post(self, data: T) -> None:
		for h in self.handlers:
			h.callback(data)


'''
	will dispatch events on the main thread if called from a background thread
	in our case we used it to make sublime events dispatch on our main thread
'''


class EventDispatchMain(Event[T], Generic[T]):
	def _post(self, data: T) -> None:
		for h in self.handlers:
			h.callback(data)

	def post(self, data: T) -> None:
		call_soon_threadsafe(self._post, data)

