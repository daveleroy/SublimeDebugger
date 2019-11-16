import os

from .core import *
from .sublime import *
from .log import *
from .event import Handle, Event, EventDispatchMain
from . import platform
from .error import Error
from .dispose import Disposables

_current_package = ""

def current_package() -> str:
	return os.path.join(sublime.packages_path(), _current_package)

def current_package_name() -> str:
	return _current_package

def startup(on_main: Callable[[], None], package_name: str) -> None:
	global _current_package
	_current_package = package_name
	print(_current_package)

	thread = threading.Thread(target=start_event_loop)
	thread.start()
	call_soon_threadsafe(on_main)

# Can be called from any thread. Do any shutdown operations in the callback.
def shutdown(on_main: Callable[[], None]) -> None:
	def shutdown_main():
		print("shutdown_main_thread")
		try:
			on_main()
		except:
			log_exception()
			log_error("There was an error while attempting to shut down the event loop")
		stop_event_loop()

	call_soon_threadsafe(shutdown_main)