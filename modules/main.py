from __future__ import annotations
from .typecheck import *

from .import ui
from .import core

from .debugger import Debugger

from .commands import Commands
from .settings import Settings

from .adapters import * #import all the adapters so Adapters.initialize() will see them
from .adapters_registry import AdaptersRegistry

import sublime
import sublime_plugin

was_opened_at_startup: Set[int] = set()

def startup() -> None:
	core.log_info('startup')
	ui.startup()

	Settings.initialize()
	AdaptersRegistry.initialize()
	Commands.initialize()

	for window in sublime.windows():
		open(window)

def shutdown() -> None:
	core.log_info('shutdown')
	for key, instance in dict(Debugger.instances).items():
		instance.dispose()
	Debugger.instances = {}
	ui.shutdown()

def exit() -> None:
	core.log_info('saving project data: {}'.format(Debugger.instances))
	for key, instance in dict(Debugger.instances).items():
		instance.save_data()

def open(window_or_view: Union[sublime.View, sublime.Window]):
	if isinstance(window_or_view, sublime.View):
		view = window_or_view
		window = view.window()
	else:
		window = window_or_view
		view = window.active_view()

	if not window:
		return

	if Settings.open_at_startup and (not window.id() in was_opened_at_startup) and Debugger.should_auto_open_in_window(window):
		was_opened_at_startup.add(window.id())
		Debugger.get(window, create=True)

def on_load_project(window: sublime.Window):
	if debugger := Debugger.get(window):
		debugger.project.reload()

def on_pre_close_window(window: sublime.Window):
	if debugger := Debugger.get(window):
		debugger.dispose()

core.on_new_window.add(open)
core.on_load_project.add(on_load_project)
core.on_pre_close_window.add(on_pre_close_window)
core.on_exit.add(exit)
