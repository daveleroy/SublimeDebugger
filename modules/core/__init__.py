from __future__ import annotations

import os
import time

from .core import *
from .sublime import *
from .event import Handle, Event, EventReturning
from . import platform
from .error import Error

from .json import json_encode, json_decode

from .log import *

_current_package = __package__.split('.', 1)[0]
_current_package_path = os.path.join(sublime.packages_path(), _current_package)

def current_package() -> str:
	return _current_package_path

def current_package_name() -> str:
	return _current_package

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
	def __init__(self, callback: Callable[[], None], interval: float, repeat: bool) -> None:
		self.interval = interval
		self.callback = callback
		self.cancelable = core.call_later(interval, self.on_complete)
		self.repeat = repeat

	def schedule(self) -> None:
		self.cancelable = core.call_later(self.interval, self.on_complete)

	def on_complete(self) -> None:
		self.callback()
		if self.repeat:
			self.schedule()

	def dispose(self) -> None:
		self.cancelable.cancel()
