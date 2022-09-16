from __future__ import annotations

import asyncio
import sublime

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

class SublimeEventLoop (asyncio.AbstractEventLoop):
	def run_forever(self):
		raise NotImplementedError

	def run_until_complete(self, future):
		raise NotImplementedError

	def stop(self):
		raise NotImplementedError

	def is_running(self):
		return True

	def is_closed(self):
		return False

	def close(self):
		raise NotImplementedError

	def shutdown_asyncgens(self):
		raise NotImplementedError

	# Methods scheduling callbacks.  All these return Handles.
	def _timer_handle_cancelled(self, handle):
		raise NotImplementedError

	def call_soon(self, callback, *args, context=None):
		handle = Handle(callback, args)
		sublime.set_timeout(handle, 0)
		return handle

	def call_later(self, delay, callback, *args, context=None):
		handle = Handle(callback, args)
		sublime.set_timeout(handle, delay * 1000)
		return handle

	def call_at(self, when, callback, *args):
		raise NotImplementedError

	def time(self):
		raise NotImplementedError

	def create_future(self):
		return asyncio.futures.Future(loop=self)

	# Method scheduling a coroutine object: create a task.
	def create_task(self, coro):
		task = asyncio.tasks.Task(coro, loop=self)
		if task._source_traceback: #type: ignore
			del task._source_traceback[-1] #type: ignore
		return task

	# Methods for interacting with threads.
	def call_soon_threadsafe(self, callback, *args):
		return self.call_later(0, callback, *args)

	def run_in_executor(self, executor, func, *args):
		raise NotImplementedError

	def set_default_executor(self, executor):
		raise NotImplementedError

	# Task factory.

	def set_task_factory(self, factory):
		raise NotImplementedError

	def get_task_factory(self):
		raise NotImplementedError

	# Error handlers.

	def get_exception_handler(self):
		raise NotImplementedError

	def set_exception_handler(self, handler):
		raise NotImplementedError

	def default_exception_handler(self, context):
		raise NotImplementedError

	def call_exception_handler(self, context):
		from .log import exception
		from .error import Error

		try:
			if 'exception' in context:
				raise context['exception']
			else:
				raise Error(context['message'])

		except Exception as e:
			exception()

	# Debug flag management.
	def get_debug(self):
		return False

	def set_debug(self, enabled):
		raise NotImplementedError
