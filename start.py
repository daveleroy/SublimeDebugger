import sys

module_starts_with = __package__ + '.'

modules_to_remove = list(filter(lambda m: m.startswith(module_starts_with) and m != __name__, sys.modules.keys()))
for m in modules_to_remove:
	del sys.modules[m]

if modules_to_remove:
	print("removed old modules: {}".format(modules_to_remove))

# import all the commands so that sublime sees them
from .modules.debugger.commands import DebuggerCommand
from .modules.debugger.view_selected_source import DebuggerReplaceContentsCommand, DebuggerShowLineCommand
from .modules.debugger.terminals.terminal_build import DebuggerBuildExecCommand

from .modules.ui.input import DebuggerInputCommand
from .modules.ui.events import ViewEventsListener

from .modules.debugger.output_panel import *

# try:
# 	dir_path = os.path.dirname(os.path.realpath(__file__))
# 	sys.path.insert(0, os.path.join(dir_path, "modules/libs"))
# 	from .modules.libs import ptvsd
# 	ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)
# except:
# 	core.log_exception()

def plugin_loaded():
	print('plugin_loaded')
	from .modules.debugger.main import startup
	startup()

def plugin_unloaded():
	print('plugin_unloaded')
	from .modules.debugger.main import shutdown
	shutdown()
