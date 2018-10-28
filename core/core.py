from sublime_db.core.typecheck import (
	Any,
	Generator,
	Callable,
	List,
	Optional,
	TypeVar,
	Generic,
	Union
)

import sublime
import threading
import concurrent

from sublime_db.libs import asyncio

T = TypeVar('T')

awaitable = Generator[Any, Any, T]
async = asyncio.coroutine

main_loop = asyncio.new_event_loop()
main_executor = concurrent.futures.ThreadPoolExecutor(max_workers = 5)

def _run_event_loop() -> None:
	print('running main event loop')
	main_loop.run_forever()

_main_thread = threading.Thread(target = _run_event_loop)
def start_event_loop() -> None:
	_main_thread.start()

def stop_event_loop() -> None:
	main_loop.stop()
	

def all_methods(decorator):
    def decorate(cls): 
        for attribute in cls.__dict__:
            if callable(getattr(cls,attribute)): 
                setattr(cls, attribute, decorator(getattr(cls, attribute)))
        return cls
    return decorate

'''decorator for requiring that a function must be run in the background'''
def require_main_thread(function):
    def wrapper(*args, **kwargs):
        assert_main_thread()
        return function(*args, **kwargs)
    return wrapper
    

def run(awaitable: awaitable[T], on_done: Optional[Callable[[T], None]] = None) -> None:
	task = main_loop.create_task(awaitable)
	if on_done:
		task.add_done_callback(lambda task, on_done=on_done: on_done(task.result())) #type: ignore

def assert_main_thread() -> None:
	assert threading.current_thread() == _main_thread, 'expecting main thread'

def display(msg: 'Any') -> None:
	sublime.error_message('{}'.format(msg))

class Error:
	def __init__(self, msg: str) -> None:
		self.msg = msg
	def __str__(self) -> str:
		return self.msg
	 	