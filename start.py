
import sys

# if not installed by package control the package name will be sublime_debugger if cloned from the git repo
if not 'debugger' in sys.modules:
	sys.modules['debugger'] = sys.modules['sublime_debugger']

import threading
import sublime

from debugger.modules.core.typecheck import Set

from debugger.modules import ui
from debugger.modules import core

# import all the commands so that sublime sees them
from debugger.modules.debugger.commands import *
from debugger.modules.debugger.output_panel import *
from debugger.modules.debugger.debugger_interface import *

from debugger.modules.ui import ViewEventsListener
from debugger.modules.ui import DebuggerInputCommand

from debugger.modules.debugger.util import get_setting

def startup() -> None:
	print('Starting up')
	ui.startup()
	ui.import_css('{}/{}'.format(core.current_package(), 'modules/debugger/components/components.css'))

	was_opened_at_startup = set() #type: Set[int]

	def on_view_activated(view: sublime.View) -> None:
		# there is probabaly a better way to filter out things like output panels and stuff
		if not view.file_name():
			return
		window = view.window()
		if get_setting(view, 'open_at_startup', False) and (not window.id() in was_opened_at_startup) and DebuggerInterface.should_auto_open_in_window(window):
			was_opened_at_startup.add(window.id())
			DebuggerInterface.for_window(window, True)

	ui.view_activated.add(on_view_activated)


def shutdown() -> None:
	print('shutdown')
	for key, instance in dict(DebuggerInterface.instances).items():
		instance.dispose()
	DebuggerInterface.instances = {}
	ui.shutdown()


def plugin_loaded():
	# um use vscode or a seperate instance of sublime for debugging this plugin or you will lockup when you hit a breakpoint...
	# import ptvsd
	# try:
	#	ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)
	# except:
	#	pass
	print('plugin_loaded')
	core.startup(startup, __package__.split('.', 1)[0])


def plugin_unloaded():
	print('plugin_unloaded')
	core.shutdown(shutdown)
