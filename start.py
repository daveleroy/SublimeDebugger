import sys
import sublime

if sublime.version() < '4000':
	raise Exception('This version of Debugger requires st4, use the st3 branch')

module_starts_with = __package__ + '.'

modules_to_remove = list(filter(lambda m: m.startswith(module_starts_with) and m != __name__, sys.modules.keys()))
for m in modules_to_remove:
	del sys.modules[m]


# import all the commands so that sublime sees them
from .modules.commands import DebuggerCommand, DebuggerExecCommand

from .modules.ui.input import DebuggerInputCommand
from .modules.core.sublime import DebuggerAsyncTextCommand, DebuggerEventsListener
from .modules.listener import Listener

from .modules.autocomplete import AutocompleteEventListener

def plugin_loaded():
	from .modules.main import startup
	startup()

def plugin_unloaded():
	from .modules.main import shutdown
	shutdown()
