from __future__ import annotations
from typing import Any, Awaitable, Callable, Coroutine, Generator, Generic, Iterable, Protocol, TypeVar, overload
from .typing import TypeVarTuple, Unpack, ParamSpec

import sublime
import concurrent
import asyncio

from .sublime_event_loop import SublimeEventLoop

T = TypeVar('T')
Args = TypeVarTuple('Args')
Params = ParamSpec('Params')

CancelledError = asyncio.CancelledError

sublime_event_loop = SublimeEventLoop() #type: ignore
sublime_event_loop_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8) #type: ignore

class Disposeable(Protocol):
	def dispose(self): ...


class Dispose:
	_dispose: list[Disposeable]|None = None

	def dispose(self):
		if not self._dispose: return

		for _dispose in self._dispose:
			_dispose.dispose()

	def dispose_remove(self, item: Disposeable):
		if not self._dispose: return

		self._dispose.remove(item)
		item.dispose()

	def dispose_add(self, item: Disposeable|list[Disposeable]):
		if not self._dispose:
			self._dispose = []

		if isinstance(item, list):
			for i in item:
				self._dispose.append(i)
		else:
			self._dispose.append(item)


D = TypeVar("D", bound="Disposeable")

def remove_and_dispose(list: list[D], filter: Callable[[D], bool]):
	remove = []
	for item in list:
		if filter(item):
			remove.append(item)

	for item in remove:
		list.remove(item)
		item.dispose()


class Future(asyncio.Future, Generic[T]):
	def __init__(self):
		super().__init__(loop=sublime_event_loop)

	def __await__(self) -> Generator[Any, None, T]:
		return super().__await__() #type: ignore

	def set_result(self, result: T) -> None:
		return super().set_result(result) #type: ignore

def call_soon_threadsafe(callback: Callable[[Unpack[Args]], None], *args: Unpack[Args]):
	return sublime_event_loop.call_soon_threadsafe(callback, *args) #type: ignore

def call_soon(callback: Callable[[Unpack[Args]], Any], *args: Unpack[Args]):
	return sublime_event_loop.call_soon(callback, *args) #type: ignore

def call_later(interval: float, callback: Callable[[Unpack[Args]], Any], *args: Unpack[Args]):
	return sublime_event_loop.call_later(interval, callback, *args) #type: ignore

def create_future() -> Future[Any]:
	return sublime_event_loop.create_future() #type: ignore

def run_in_executor(func: Callable[[Unpack[Args]], T], *args: Unpack[Args]) -> Future[T]:
	return asyncio.futures.wrap_future(sublime_event_loop_executor.submit(func, *args), loop=sublime_event_loop) #type: ignore

def wait(fs: Iterable[Awaitable[Any]]) -> Awaitable[list[Any]]:
	return asyncio.wait(fs, loop=sublime_event_loop) #type: ignore

def sleep(delay: float) -> Awaitable[None]:
	return asyncio.sleep(delay, loop=sublime_event_loop) #type: ignore

def gather(*coros_or_futures: Awaitable[T]) -> Awaitable[tuple[T]]:
	return asyncio.gather(*coros_or_futures, loop=sublime_event_loop) #type: ignore

def gather_results(*coros_or_futures: Awaitable[T]) -> Awaitable[list[T|Exception]]:
	return asyncio.gather(*coros_or_futures, loop=sublime_event_loop, return_exceptions=True) #type: ignore

@overload
def run(value: Callable[Params, Coroutine[Any, Any, T]], *args: Any) -> Callable[Params, Future[T]]: ...

@overload
def run(value: Awaitable[T], on_success: Callable[[T], None] | None = None, on_error: Callable[[BaseException], None] | None = None) -> Future[T]: ...

def run(value: Awaitable[T] | Callable[Params, Coroutine[Any, Any, T]], on_success: Callable[[T], None] | None = None, on_error: Callable[[BaseException], None] | None = None, *args: Any, **kwargs: Any) -> Any:
	if callable(value):
		def wrap(*args, **kwargs):
			return asyncio.ensure_future(value(*args, **kwargs), loop=sublime_event_loop) #type: ignore
		wrap.__name__ = value.__name__ #type: ignore
		return wrap

	task: Future[T] = asyncio.ensure_future(value, loop=sublime_event_loop) #type: ignore

	def done(task: asyncio.Future[T]) -> None:
		if on_error:
			try: 
				result = task.result()
				if on_success: on_success(result)

			except BaseException as e: 
				on_error(e)

		elif on_success:
			result = task.result()
			on_success(result)

	if on_error or on_success:
		task.add_done_callback(done)

	return task

def display(msg: 'Any'):
	sublime.error_message('{}'.format(msg))
