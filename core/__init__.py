
from .core import *
from .sublime import *
from .event import Handle, Event, EventDispatchMain

def startup () -> None:
	start_event_loop()

def shutdown () -> None:
	stop_event_loop()