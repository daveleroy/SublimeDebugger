
should_log_exceptions = True
should_log_error = True
should_log_info = True


def log_error(*args) -> None:
	if not should_log_error:
		return
	print(*args)


def log_exception(*args) -> None:
	import traceback
	if not should_log_exceptions:
		return
	print(*args, end='')
	print(traceback.format_exc())


def log_info(*args) -> None:
	if not should_log_info:
		return
	print(*args)
