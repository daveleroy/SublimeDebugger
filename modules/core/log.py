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
	print('Debugger: ❗', *args)


def alert(*args: Any) -> None:
	sublime.error_message(str(args))

	if not _should_log_error:
		return
	print('Debugger: ❗', *args)


def exception(*args: Any) -> None:
	if not _should_log_exceptions:
		return

	if args:
		print('Debugger: ❗', *args)
	else:
		print('Debugger: ❗', 'Exception')

	print(traceback.format_exc())


def debug(*args: Any) -> None:
	if not _should_log_info:
		return
	print('Debugger:', *args)
