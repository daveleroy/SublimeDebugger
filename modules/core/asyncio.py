from __future__ import annotations

import asyncio
import sublime
from concurrent.futures import ThreadPoolExecutor

from typing import Any, Awaitable, Callable, Coroutine, Generator, Generic, Iterable, TypeVar, overload
from .typing_extensions import TypeVarTuple, Unpack, ParamSpec

CancelledError = asyncio.CancelledError

T = TypeVar('T')
Args = TypeVarTuple('Args')
Params = ParamSpec('Params')


class Future(asyncio.Future, Generic[T]):
	def __init__(self):
		super().__init__(loop=loop)

	def __await__(self) -> Generator[Any, None, T]:
		return super().__await__() #type: ignore

	def set_result(self, result: T) -> None:
		return super().set_result(result) #type: ignore

def call_soon(callback: Callable[[Unpack[Args]], Any], *args: Unpack[Args]):
	return loop.call_soon(callback, *args)

def call_later(interval: float, callback: Callable[[Unpack[Args]], Any], *args: Unpack[Args]):
	return loop.call_later(interval, callback, *args)

def run_in_executor(func: Callable[Params, T]) -> Callable[Params, Future[T]]:
	def wrap(*args, **kwargs):
		return asyncio.futures.wrap_future(executor.submit(func, *args, **kwargs), loop=loop) #type: ignore
	wrap.__name__ = func.__name__
	return wrap #type: ignore


def wait(fs: Iterable[Awaitable[Any]]) -> Awaitable[list[Any]]:
	return asyncio.wait(fs, loop=loop) #type: ignore

def delay(seconds: float) -> Awaitable[None]:
	future = Future()
	sublime.set_timeout(lambda: future.set_result(None), seconds * 1000)
	return future

def gather(*coros_or_futures: Awaitable[T]) -> Awaitable[tuple[T]]:
	return asyncio.gather(*coros_or_futures, loop=loop) #type: ignore

def gather_results(*coros_or_futures: Awaitable[T]) -> Awaitable[list[T|Exception]]:
	return asyncio.gather(*coros_or_futures, loop=loop, return_exceptions=True) #type: ignore

@overload
def run(value: Callable[Params, Coroutine[Any, Any, T]], *args: Any) -> Callable[Params, Future[T]]: ...

@overload
def run(value: Awaitable[T], on_success: Callable[[T], None] | None = None, on_error: Callable[[BaseException], None] | None = None) -> Future[T]: ...

def run(value: Awaitable[T] | Callable[Params, Coroutine[Any, Any, T]], on_success: Callable[[T], None] | None = None, on_error: Callable[[BaseException], None] | None = None, *args: Any, **kwargs: Any) -> Any:
	if callable(value):
		def wrap(*args, **kwargs):
			return asyncio.ensure_future(value(*args, **kwargs), loop=loop) #type: ignore
		wrap.__name__ = value.__name__ #type: ignore
		return wrap

	task: Future[T] = asyncio.ensure_future(value, loop=loop) #type: ignore

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

class Handle:
	def __init__(self, callback, args):
		self.callback = callback
		self.args = args

	def __call__(self):
		if self.callback:
			self.callback(*self.args)

	def cancel(self):
		self.callback = None
		self.args = None

class SublimeEventLoop (asyncio.BaseEventLoop):
	def is_running(self):
		return True

	def is_closed(self):
		return False

	def call_soon(self, callback, *args, context=None): #type: ignore
		handle = Handle(callback, args)
		sublime.set_timeout(handle, 0)
		return handle

	def call_later(self, delay, callback, *args, context=None): #type: ignore
		handle = Handle(callback, args)
		sublime.set_timeout(handle, delay * 1000)
		return handle

	def create_future(self):
		return asyncio.futures.Future(loop=self)

	# Method scheduling a coroutine object: create a task.
	def create_task(self, coro): #type: ignore
		task = asyncio.tasks.Task(coro, loop=self)
		task._log_destroy_pending = False #type: ignore

		if task._source_traceback: #type: ignore
			del task._source_traceback[-1] #type: ignore
		return task

	# Methods for interacting with threads.
	def call_soon_threadsafe(self, callback, *args): #type: ignore
		handle = Handle(callback, args)
		sublime.set_timeout(handle, 0)
		return handle

	# Debug flag management.
	def get_debug(self):
		return False

loop = SublimeEventLoop()
executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix='DebuggerThreadPool')
