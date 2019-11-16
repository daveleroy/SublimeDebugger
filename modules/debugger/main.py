from .. typecheck import *
from .. import ui
from .. import core

from .debugger_interface import DebuggerInterface
from .util import get_setting

import sublime


def shutdown() -> None:
	def on_main():
		print('shutting down: {}'.format(DebuggerInterface.instances))
		for key, instance in dict(DebuggerInterface.instances).items():
			print(instance)
			instance.dispose()
		DebuggerInterface.instances = {}
		ui.shutdown()

	core.shutdown(on_main)
	

def startup() -> None:
	def on_main():
		print('Starting up')
		ui.startup()
		ui.import_css('{}/{}'.format(core.current_package(), 'modules/components/components.css'))

		was_opened_at_startup = set() #type: Set[int]

		def on_view_activated(view: sublime.View) -> None:
			# there is probabaly a better way to filter out things like output panels and stuff
			if not view.file_name():
				return
			window = view.window()
			if get_setting(view, 'open_at_startup', False) and (not window.id() in was_opened_at_startup) and DebuggerInterface.should_auto_open_in_window(window):
				was_opened_at_startup.add(window.id())
				DebuggerInterface.for_window(window, create=True)

		ui.view_activated.add(on_view_activated)

	core.startup(on_main, __package__.split('.', 1)[0])