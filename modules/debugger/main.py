from .. typecheck import *
from .. import ui
from .. import core

from .debugger_interface import DebuggerInterface
from .util import get_setting

import sublime


def shutdown() -> None:
	global instances
	print('shutting down: {}'.format(Debugger.instances))
	for key, instance in dict(Debugger.instances).items():
		print(instance)
		instance.dispose()
	Debugger.instances = {}
	ui.shutdown()


def startup() -> None:
	ui.startup()
	was_opened_at_startup = set() #type: Set[int]

	def on_view_activated(view: sublime.View) -> None:
		# there is probabaly a better way to filter out things like output panels and stuff
		if not view.file_name():
			return
		window = view.window()
		if get_setting(view, 'open_at_startup', False) and (not window.id() in was_opened_at_startup) and Debugger.should_auto_open_in_window(window):
			was_opened_at_startup.add(window.id())
			Debugger.for_window(window, create=True)

	ui.view_activated.add(on_view_activated)

	# open for active view at least
	window = sublime.active_window()
	view = window and window.active_view()
	if view:
		on_view_activated(view)
