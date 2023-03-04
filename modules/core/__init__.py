from __future__ import annotations

import os
import time

from .util import *
from .core import *
from .sublime import *
from .event import Handle, Event, EventReturning
from . import platform
from .error import Error
from .json import json_encode, json_decode, JSON
from .log import *
from .asyncio import (
	Future,
	CancelledError,

	call_later,
	call_soon,
	delay,
	run,
	run_in_executor,

	gather,
	gather_results,
)

_current_package = __package__.split('.', 1)[0]
_current_package_path = os.path.join(sublime.packages_path(), _current_package)

def package_path(*components: str) -> str:
	if components:
		return os.path.join(_current_package_path, *components)
	return _current_package_path

def package_path_relative(component: str) -> str:
	# WARNING!!! dont change to os.path.join sublime doesn't like back slashes in add_region? and other places?
	return f'Packages/{_current_package}/{component}'


class stopwatch:
	def __init__(self, prefix: str = '') -> None:
		self.ts = time.time()
		self.prefix = prefix

	def __call__(self, postfix='') -> None:
		self.print(postfix)

	def print(self, postfix=''):
		te = time.time()
		print ('%s: %2.2f ms %s' %  (self.prefix.rjust(8), (te - self.ts) * 1000, postfix))

	def elapsed(self):
		te = time.time()
		return (te - self.ts) * 1000

class timer:
	def __init__(self, callback: Callable[[], Any], interval: float, repeat: bool = False) -> None:
		self.interval = interval
		self.callback = callback
		self.cancelable = call_later(interval, self.on_complete)
		self.repeat = repeat

	def schedule(self) -> None:
		self.cancelable = call_later(self.interval, self.on_complete)

	def on_complete(self) -> None:
		self.callback()
		if self.repeat:
			self.schedule()

	def dispose(self) -> None:
		self.cancelable.cancel()
