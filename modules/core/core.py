from ..typecheck import *

import sublime
import threading
import concurrent

from ..libs import asyncio
from .log import log_exception
from .error import Error

T = TypeVar('T')

awaitable = Generator[Any, Any, T]
coroutine = asyncio.coroutine
future = asyncio.Future
CancelledError = asyncio.CancelledError

_main_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

def _create_main_loop():
	def _exception_handler(loop: Any, context: dict) -> None:
		print('An exception occured in the main_loop')
		try:
			if 'exception' in context:
				raise context['exception']
			else:
				raise Error(context['message'])
		except:
			log_exception()

	loop = asyncio.new_event_loop()
	loop.set_exception_handler(_exception_handler)
	return loop

_main_loop = _create_main_loop()
_main_thread = None

def call_soon_threadsafe(callback, *args):
	return _main_loop.call_soon_threadsafe(callback, *args)


def call_soon(callback, *args):
	return _main_loop.call_soon(callback, *args)


def call_later(interval, callback, *args):
	return _main_loop.call_later(interval, callback, *args)


def create_future():
	return _main_loop.create_future()


def run_in_executor(callable, *args):
	return _main_loop.run_in_executor(_main_executor, callable, *args)

_main_loop_future = None #type: Optional[Future]

def start_event_loop() -> None:
	print('start_event_loop')
	global _main_thread
	global _main_loop
	global _main_loop_future
	_main_thread = threading.current_thread()
	_main_loop_future = _main_loop.create_future()
	_main_loop.run_until_complete(_main_loop_future)

def stop_event_loop() -> None:
	global _main_thread
	global _main_loop
	global _main_loop_future
	_main_loop_future.set_result(True)


def all_methods(decorator):
	def decorate(cls):
		for attribute in cls.__dict__:
			if callable(getattr(cls, attribute)):
				setattr(cls, attribute, decorator(getattr(cls, attribute)))
		return cls
	return decorate


'''decorator for requiring that a function must be run in the background'''
def require_main_thread(function):
	def wrapper(*args, **kwargs):
		assert_main_thread()
		return function(*args, **kwargs)
	return wrapper


def run(awaitable: awaitable[T], on_done: Callable[[T], None] = None, on_error: Callable[[Exception], None] = None) -> asyncio.Future:
	task = asyncio.ensure_future(awaitable, loop=_main_loop)

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

def assert_main_thread() -> None:
	assert is_main_thred(), 'expecting main thread'


def is_main_thred() -> bool:
	return threading.current_thread() == _main_thread


def display(msg: 'Any') -> None:
	sublime.error_message('{}'.format(msg))

