from ..typecheck import *

import sublime
import threading
import concurrent
import asyncio

from .log import log_exception
from .error import Error
from .sublime_event_loop import SublimeEventLoop

T = TypeVar('T')
awaitable = Awaitable[T]
coroutine = asyncio.coroutine
future = asyncio.Future
CancelledError = asyncio.CancelledError

sublime_event_loop = SublimeEventLoop()
sublime_event_loop_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
asyncio.set_event_loop(sublime_event_loop)

def call_soon_threadsafe(callback, *args):
	return sublime_event_loop.call_soon(callback, *args)

def call_soon(callback, *args):
	return sublime_event_loop.call_soon(callback, *args)

def call_later(interval, callback, *args):
	return sublime_event_loop.call_later(interval, callback, *args)

def create_future():
	return sublime_event_loop.create_future()

def run_in_executor(func, *args):
	return asyncio.futures.wrap_future(sublime_event_loop_executor.submit(func, *args), loop=sublime_event_loop)

def wait(fs: Iterable[awaitable[T]]):
	return asyncio.wait(fs, loop=sublime_event_loop)

def sleep(delay: float) -> Awaitable[None]:
	return asyncio.sleep(delay, loop=sublime_event_loop)

def schedule(func: T, *args):
	def wrap(*args):
		return asyncio.ensure_future(func(*args), loop=sublime_event_loop) #type: ignore
	wrap.__name__ = func.__name__ #type: ignore
	return wrap

def run(awaitable: awaitable[T], on_done: Callable[[T], None] = None, on_error: Callable[[Exception], None] = None) -> future:
	task = asyncio.ensure_future(awaitable, loop=sublime_event_loop)

	def done(task) -> None:
		exception = task.exception()

		if on_error and exception:
			on_error(exception)

			try:
				raise exception
			except Exception as e:
				log_exception()

			return

		result = task.result()
		if on_done:
			on_done(result)

	task.add_done_callback(done)
	return task

def display(msg: 'Any') -> None:
	sublime.error_message('{}'.format(msg))
