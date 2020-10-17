from ..typecheck import *

import sublime
import sublime_plugin

from .core import call_soon_threadsafe, create_future, coroutine, awaitable, schedule
from .event import Event
from .error import Error

async def sublime_open_file_async(window: sublime.Window, file: str, line: Optional[int] = None, column: Optional[int] = None) -> sublime.View:
	if line:
		file += f':{line}'
	if column:
		file += f':{column}'

	view = window.open_file(file, sublime.ENCODED_POSITION)
	await wait_for_view_to_load(view)
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
		print("there was already an active edit..?")

	DebuggerAsyncTextCommand._run = run
	view.run_command('debugger_async_text')

on_view_modified: Event[sublime.View] = Event()
on_view_load: Event[sublime.View] = Event()
on_view_hovered: Event[Tuple[sublime.View, int, int]] = Event()
on_view_activated: Event[sublime.View] = Event()
on_view_gutter_clicked: Event[Tuple[sublime.View, int, int]] = Event() # view, line, button
on_view_drag_select_or_context_menu: Event[sublime.View] = Event()

on_load_project: Event[sublime.Window] = Event()
on_new_window: Event[sublime.Window] = Event()
on_pre_close_window: Event[sublime.Window] = Event()
on_exit: Event[sublime.Window] = Event()

on_pre_hide_panel: Event[sublime.Window] = Event()
on_post_show_panel: Event[sublime.Window] = Event()

class DebuggerAsyncTextCommand(sublime_plugin.TextCommand):
	_run = None

	def run(self, edit: sublime.Edit):
		try:
			DebuggerAsyncTextCommand._run(edit)
			DebuggerAsyncTextCommand._run = None
		except Exception as e:
			DebuggerAsyncTextCommand._run = None
			raise e

class DebuggerEventsListener(sublime_plugin.EventListener):

	# detects clicks on the gutter
	# if a click is detected we then reselect the previous selection
	# This means that a click in the gutter no longer selects that line (at least when a debugger is open)
	def on_text_command(self, view: sublime.View, cmd: str, args: dict) -> Any:
		# why bother doing this work if no one wants it
		if not on_view_gutter_clicked and not on_view_drag_select_or_context_menu:
			return

		if (cmd == 'drag_select' or cmd == 'context_menu') and 'event' in args:
			on_view_drag_select_or_context_menu(view)

			event = args['event']

			view_x, view_y = view.layout_to_window(view.viewport_position()) #type: ignore

			x = event['x']
			y = event['y']

			margin = view.settings().get("margin") or 0
			offset = x - view_x

			if offset < -30 - margin:
				pt = view.window_to_text((x, y))
				line = view.rowcol(pt)[0]

				# only rewrite this command if someone actually consumed it
				# otherwise let sublime do its thing
				if on_view_gutter_clicked((view, line, event['button'])):
					return ("null", {})

	def on_window_command(self, window, command_name, args):
		if command_name == 'hide_panel':
			if on_pre_hide_panel(window):
				return ("null", {})

	def on_post_window_command(self, window, command_name, args):
		if command_name == 'show_panel':
			on_post_show_panel(window)

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
