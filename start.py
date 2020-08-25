import sys
import sublime

if sublime.version() < '4000':
	raise Exception('This version of Debugger requires st4, use the st3 branch')

module_starts_with = __package__ + '.'

modules_to_remove = list(filter(lambda m: m.startswith(module_starts_with) and m != __name__, sys.modules.keys()))
for m in modules_to_remove:
	del sys.modules[m]

# import all the commands so that sublime sees them
from .modules.debugger.commands import DebuggerCommand
from .modules.debugger.view_selected_source import DebuggerReplaceContentsCommand, DebuggerShowLineCommand
from .modules.debugger.terminals.terminal_build import DebuggerExecCommand

from .modules.ui.input import DebuggerInputCommand
from .modules.core.sublime import DebuggerAsyncTextCommand, DebuggerEventsListener

# try:
# 	dir_path = os.path.dirname(os.path.realpath(__file__))
# 	sys.path.insert(0, os.path.join(dir_path, "modules/libs"))
# 	from .modules.libs import ptvsd
# 	ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)
# except:
# 	core.log_exception()

def plugin_loaded():
	from .modules.debugger.main import startup
	startup()

def plugin_unloaded():
	from .modules.debugger.main import shutdown
	shutdown()
