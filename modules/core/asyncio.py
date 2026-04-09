# If sublime_aio gets its head out of its ass and supports async/await in the main thread (its basically fucking trivial) we could remove all this shit.
# Most of the workarounds here are to prevent this event loop from being set as the current one on the main thread so as to not allow any other packages to use it...
# https://github.com/packagecontrol/sublime_aio

from __future__ import annotations

import asyncio
import sublime
import math

from typing import Any, Awaitable, Callable, Coroutine, TypeVar, overload
from .typing_extensions import TypeVarTuple, Unpack, ParamSpec

import atexit
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor



T = TypeVar('T')
A = TypeVar('A')
B = TypeVar('B')
Args = TypeVarTuple('Args')
Params = ParamSpec('Params')


class Handle:
	def __init__(self, callback, args):
		self.callback = callback
		self.args = args

	def __call__(self):

		if self.callback:
			# this isn't needed if asyncio._set_running_loop(main_loop) is used...
			loop = asyncio._get_running_loop()
			asyncio._set_running_loop(main_loop)
			self.callback(*self.args)
			asyncio._set_running_loop(loop) # undo


	def cancel(self):
		self.callback = None
		self.args = None


class MainEventLoop(asyncio.BaseEventLoop):
	def __init__(self) -> None:
		super().__init__()
		assert threading.currentThread() == threading.main_thread()


	# We dont want to main loop set in the hopes sublime_aio gets its head out of its ass
	def run_forever(self) -> None:
		loop = asyncio._get_running_loop()
		self._run_forever_setup() # type: ignore
		asyncio._set_running_loop(loop) # undo

	# We dont want to main loop cleared in the hopes sublime_aio gets its head out of its ass
	def run_forever_stop(self) -> None:
		loop = asyncio._get_running_loop()
		self._run_forever_cleanup() # type: ignore
		asyncio._set_running_loop(loop) # undo

	def call_soon(self, callback, *args, context=None):  # type: ignore
		handle = Handle(callback, args)
		sublime.set_timeout(handle, 0)
		return handle

	def call_later(self, delay, callback, *args, context=None):  # type: ignore
		handle = Handle(callback, args)
		sublime.set_timeout(handle, int(delay * 1000))
		return handle

	def create_future(self):
		return asyncio.futures.Future(loop=self)


	# Method scheduling a coroutine object: create a task.
	def create_task(self, coro):  # type: ignore
		task = asyncio.tasks.Task(coro, loop=self)
		task._log_destroy_pending = False  # type: ignore

		if task._source_traceback:  # type: ignore
			del task._source_traceback[-1]  # type: ignore
		return task

	# Methods for interacting with threads.
	def call_soon_threadsafe(self, callback, *args):  # type: ignore
		handle = Handle(callback, args)
		sublime.set_timeout(handle, 0)
		return handle

	# Debug flag management.
	def get_debug(self):
		return True

	# we can actually delegate these io primatives to the background loop, works fine... or not and just say they are unimplemented in the main loop
	async def subprocess_shell(self, *args, **kwargs):
		return await create_task_background(background_loop.subprocess_shell(*args, **kwargs))

	async def subprocess_exec(self, *args, **kwargs):
		return await create_task_background(background_loop.subprocess_exec(*args, **kwargs))

	async def create_server(self, *args, **kwargs):
		return await create_task_background(background_loop.create_server(*args, **kwargs))


main_loop = MainEventLoop()
main_loop.run_forever()

background_loop = asyncio.new_event_loop()
executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix='DebuggerThreadPool')

# this sets the global event loop for the main thread (the debugger package can't set this but an official asyncio library could)
# asyncio._set_running_loop(main_loop)

background_thread = threading.Thread(target=lambda: (background_loop.run_forever(), background_loop.close()))
background_thread.start()


def get_running_loop():
	if threading.current_thread() == threading.main_thread():
		return main_loop
	return


def _task_done(task):
	try:
		exc = task.exception()
		if exc:
			traceback.print_exception(type(exc), exc, exc.__traceback__)

	except asyncio.exceptions.CancelledError:
		...


def _handle_future_error(task: asyncio.Future):
	task.add_done_callback(_task_done)
	return task


# create a task on the current loop
def create_task(coroutine: Coroutine[A, B, T]):
	# this isn't needed if asyncio._set_running_loop(main_loop) is called
	loop = get_running_loop()
	if loop == main_loop:
		return create_task_main(coroutine)

	return _handle_future_error(asyncio.create_task(coroutine))

# create a task on the main loop from any other loop
def create_task_main(coroutine: Coroutine[A, B, T], loop=get_running_loop()):  # loop paramter not needed if _set_running_loop
	task = asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coroutine, main_loop), loop=loop)
	return _handle_future_error(task)


# create a task on the background loop from any other loop
def create_task_background(coroutine: Coroutine[A, B, T], loop=get_running_loop()):  # loop paramter not needed if _set_running_loop
	task = asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coroutine, background_loop), loop=loop)
	return _handle_future_error(task)


@atexit.register
def shutdown():
	def _cancel_tasks(loop: asyncio.AbstractEventLoop):
		print(f'Debugger: asyncio cancel {len(asyncio.all_tasks(loop))} tasks')
		for task in asyncio.all_tasks(loop):
			task.cancel()

		loop.stop()

	print('Debugger: asyncio starting shutdown')
	background_loop.call_soon_threadsafe(lambda: _cancel_tasks(background_loop))
	background_thread.join()


	for task in asyncio.all_tasks(main_loop):
		task.cancel()

	main_loop.stop()
	main_loop.run_forever_stop()

	print('Debugger: asyncio shutdown')


# these overrides are really only needed because we are not setting the event loop globally (a dedicated asyncio package would do that)
def override_loop(fn: Callable[Params, T]) -> Callable[Params, T]:
	def wrap(*args, **kwargs):
		if 'loop' not in kwargs:
			kwargs['loop'] = get_running_loop()

		return fn(*args, **kwargs)

	return wrap


Future = override_loop(asyncio.Future)
create_subprocess_exec = override_loop(asyncio.create_subprocess_exec)
create_subprocess_shell = override_loop(asyncio.create_subprocess_shell)
wait = override_loop(asyncio.wait)
wrap_future = override_loop(asyncio.wrap_future)
ensure_future = override_loop(asyncio.ensure_future)


def run_in_executor(func: Callable[Params, T]) -> Callable[Params, asyncio.Future[T]]:
	def wrap(*args, **kwargs):
		return wrap_future(executor.submit(func, *args, **kwargs))  # type: ignore

	wrap.__name__ = func.__name__
	return wrap  # type: ignore


CancelledError = asyncio.CancelledError


def call_soon(callback: Callable[[Unpack[Args]], Any], *args: Unpack[Args]):
	return main_loop.call_soon(callback, *args)  # type: ignore


def call_later(interval: float, callback: Callable[[Unpack[Args]], Any], *args: Unpack[Args]):
	return main_loop.call_later(interval, callback, *args)  # type: ignore


def delay(seconds: float) -> Awaitable[None]:
	future = Future()
	sublime.set_timeout(lambda: future.set_result(None), math.floor(seconds * 1000))
	return future


def gather(*coros_or_futures: Awaitable[T]) -> Awaitable[tuple[T]]:
	return asyncio.gather(*coros_or_futures)  # type: ignore


def gather_results(*coros_or_futures: Awaitable[T]) -> Awaitable[list[T | Exception]]:
	return asyncio.gather(*coros_or_futures, return_exceptions=True)  # type: ignore



@overload
def run(value: Callable[Params, Coroutine[Any, Any, T]], *args: Any) -> Callable[Params, asyncio.Future[T]]: ...


@overload
def run(value: Awaitable[T], on_success: Callable[[T], None] | None = None, on_error: Callable[[BaseException], None] | None = None) -> asyncio.Future[T]: ...

def run(value: Awaitable[T] | Callable[Params, Coroutine[Any, Any, T]], on_success: Callable[[T], None] | None = None, on_error: Callable[[BaseException], None] | None = None, *args: Any, **kwargs: Any) -> Any:
	if callable(value):
		def wrap(*args, **kwargs):
			return ensure_future(value(*args, **kwargs))  # type: ignore

		wrap.__name__ = value.__name__  # type: ignore
		return wrap

	task: Future[T] = ensure_future(value)  # type: ignore

	def done(task: asyncio.Future[T]) -> None:
		if on_error:
			try:
				result = task.result()
				if on_success:
					on_success(result)

			except BaseException as e:
				on_error(e)

		elif on_success:
			result = task.result()
			on_success(result)

	if on_error or on_success:
		task.add_done_callback(done)

	return task

T = TypeVar('T')
Args = TypeVarTuple('Args')
Params = ParamSpec('Params')


def on_background(coroutine: Callable[Params, Coroutine[Any, Any, T]], *args: Params.args, **kwargs: Params.kwargs):
	def wrap(*args, **kwargs):
		return create_task_background(coroutine(*args, **kwargs))

	wrap.__name__ = coroutine.__name__  # type: ignore
	return wrap


def on_main(coroutine: Callable[Params, Coroutine[Any, Any, T]], *args: Params.args, **kwargs: Params.kwargs):
	def wrap(*args, **kwargs):
		return create_task_main(coroutine(*args, **kwargs))

	wrap.__name__ = coroutine.__name__  # type: ignore
	return wrap
