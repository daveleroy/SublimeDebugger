from ..typecheck import *

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


def log_error(*args) -> None:
	if not _should_log_error:
		return
	print(*args)


def log_exception(*args) -> None:
	import traceback
	if not _should_log_exceptions:
		return
	print(*args, end='')
	print(traceback.format_exc())


def log_info(*args) -> None:
	if not _should_log_info:
		return
	print(*args)


class Logger(Protocol):
	def error(self, value: str):
		...
	def info(self, value: str):
		...

class StdioLogger:
	def error(self, value: str):
		print('error:', value)
	def info(self, value: str):
		print('info:', value)

stdio = StdioLogger()