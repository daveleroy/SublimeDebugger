from ..typecheck import *

import sublime
import sublime_plugin

from .core import call_soon_threadsafe, create_future, coroutine, awaitable, schedule
from .event import Event
from .error import Error

async def sublime_open_file_async(window: sublime.Window, file: str, line: Optional[int] = None) -> sublime.View:
	view = window.open_file(file)
	await wait_for_view_to_load(view)
	if line is None:
		return view
	view.show(view.text_point(line, 0), True)
	return view

async def wait_for_view_to_load(view: sublime.View):
	if view.is_loading():
		future_view = create_future()

		def loaded_view(v: sublime.View) -> None:
			if view.id() == v.id():
				future_view.set_result(view)

		handle = on_view_load.add(loaded_view)
		await future_view
		handle.dispose()

def edit(view, run):
	if DebuggerAsyncTextCommand._run:
		raise Error("There is already an active edit")

	DebuggerAsyncTextCommand._run = run
	view.run_command('debugger_async_text')

on_view_modified: Event[sublime.View] = Event()
on_view_load: Event[sublime.View] = Event()
on_view_hovered: Event[Tuple[sublime.View, int, int]] = Event()
on_view_activated: Event[sublime.View] = Event()

on_load_project: Event[sublime.Window] = Event()
on_new_window: Event[sublime.Window] = Event()
on_pre_close_window: Event[sublime.Window] = Event()
on_exit: Event[sublime.Window] = Event()

class DebuggerAsyncTextCommand(sublime_plugin.TextCommand):
	_run = None

	def run(self, edit: sublime.Edit):
		DebuggerAsyncTextCommand._run(edit)
		DebuggerAsyncTextCommand._run = None

class DebuggerEventsListener(sublime_plugin.EventListener):
	def on_hover(self, view: sublime.View, point: int, hover_zone: int) -> None:
		on_view_hovered((view, point, hover_zone))

	def on_modified(self, view: sublime.View) -> None:
		on_view_modified(view)

	def on_load(self, view: sublime.View) -> None:
		on_view_load(view)

	def on_activated(self, view: sublime.View) -> None:
		on_view_activated(view)

	def on_load_project(self, window: sublime.Window):
		on_load_project(window)

	def on_new_window(self, window: sublime.Window):
		on_new_window(window)

	def on_pre_close_window(self, window: sublime.Window):
		on_pre_close_window(window)

	def on_exit(self):
		on_exit()
