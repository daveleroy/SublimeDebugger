
from .core import *
from .sublime import *
from .event import Handle, Event, EventDispatchMain


def startup(on_main: Callable[[], None]) -> None:
	start_event_loop()
	main_loop.call_soon_threadsafe(on_main)


# Can be called from any thread. Do any shutdown operations in the callback.
# If it is not called from our main thread it will block the calling thread until it completes
def shutdown(on_main: Callable[[], None]) -> None:
	event = threading.Event()

	def shutdown_main_thread() -> None:
		try:
			on_main()
		except Exception as e:
			log_exception()
			log_error("There was an error while attempting to shut down the event loop")
		finally:
			event.set()

	if core.is_main_thred():
		shutdown_main_thread()
	else:
		core.main_loop.call_soon_threadsafe(shutdown_main_thread)
		event.wait()

	stop_event_loop()
