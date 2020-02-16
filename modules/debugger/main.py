from .. typecheck import *
from .. import ui
from .. import core

from .debugger import Debugger
from .util import get_setting

import sublime
import sublime_plugin


def startup() -> None:
	print('starting up: {}'.format(sublime.windows()))

	ui.startup()
	from .adapter import Adapters
	Adapters.initialize()

	for window in sublime.windows():
		open(window)

def shutdown() -> None:
	print('shutting down: {}'.format(Debugger.instances))
	for key, instance in dict(Debugger.instances).items():
		instance.dispose()
	Debugger.instances = {}
	ui.shutdown()

def exit() -> None:
	print('saving project data: {}'.format(Debugger.instances))
	for key, instance in dict(Debugger.instances).items():
		instance.save_data()


was_opened_at_startup: Set[int] = set()

def open(window_or_view: Union[sublime.View, sublime.Window]):
	if isinstance(window_or_view, sublime.View):
		view = window_or_view 
		window = view.window()
	else:
		window = window_or_view
		view = window.active_view()

	if get_setting(view, 'open_at_startup', False) and (not window.id() in was_opened_at_startup) and Debugger.should_auto_open_in_window(window):
		was_opened_at_startup.add(window.id())
		Debugger.for_window(window, create=True)

class MainEventListener (sublime_plugin.EventListener):	
	def on_post_save_project(self, window: sublime.Window):
		if debugger := Debugger.get(window):
			debugger.project.reload()

	def on_new_window(self, window: sublime.Window):
		open(window)

	def on_pre_close_window(self, window: sublime.Window):
		if debugger := Debugger.get(window):
			debugger.dispose()

	def on_exit(self):
		exit()