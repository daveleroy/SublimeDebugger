from __future__ import annotations
from typing import Any, Protocol

import sublime
import traceback

_should_log_exceptions = True
_should_log_error = True
_should_log_info = True


def log_configure(log_info: bool, log_errors: bool, log_exceptions: bool):
	global _should_log_exceptions
	global _should_log_error
	global _should_log_info

	_should_log_exceptions = log_exceptions
	_should_log_error = log_errors
	_should_log_info = log_info

def info(*args: Any) -> None:
	if not _should_log_info:
		return
	print('Debugger:', *args)

def error(*args: Any) -> None:
	if not _should_log_error:
		return
	print('Debugger: error:', *args)

def alert(*args: Any) -> None:
	sublime.error_message(str(args))

	if not _should_log_error:
		return
	print('Debugger: error:', *args)

def exception(*args: Any) -> None:
	if not _should_log_exceptions:
		return

	if args:
		print('Debugger: error:', *args)
	print(traceback.format_exc())


def debug(*args: Any) -> None:
	if not _should_log_info:
		return
	print('Debugger:', *args)


class Logger(Protocol):
	def log(self, type: str, value: Any):
		print(f'Debugger: {type}: {value}')

	def __call__(self, type: str, value: Any):
		self.log(type, value)

	def error(self, text: str):
		self.log('error', text)

	def warn(self, text: str):
		self.log('warn', text)

	def info(self, text: str):
		self.log('info', text)

class StdioLogger(Logger):
	def log(self, type: str, value: Any):
		print(f'Debugger: {type}: {value}')


stdio = StdioLogger()
