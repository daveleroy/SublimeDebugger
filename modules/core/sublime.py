from __future__ import annotations
from typing import Any, Callable

import sublime
import sublime_plugin

from .asyncio import Future
from .event import Event

async def sublime_open_file_async(window: sublime.Window, file: str, line: int|None = None, column: int|None = None, group: int=-1) -> sublime.View:
	if line:
		file += f':{line}'
	if column:
		file += f':{column}'

	view = window.open_file(file, sublime.ENCODED_POSITION, group=group)
	await wait_for_view_to_load(view)
	return view

async def wait_for_view_to_load(view: sublime.View):
	if view.is_loading():
		future_view: Future[sublime.View] = Future()

		def loaded_view(v: sublime.View) -> None:
			if view.id() == v.id():
				future_view.set_result(view)

		handle = on_view_load.add(loaded_view)
		await future_view
		handle.dispose()

def edit(view: sublime.View, run: Callable[[sublime.Edit], Any]):
	previous = DebuggerAsyncTextCommand._run
	DebuggerAsyncTextCommand._run = run
	view.run_command('debugger_async_text')
	DebuggerAsyncTextCommand._run = previous


on_view_load: Event[sublime.View] = Event()

on_pre_hide_panel: Event[sublime.Window, str] = Event()
on_post_show_panel: Event[sublime.Window] = Event()

class DebuggerAsyncTextCommand(sublime_plugin.TextCommand):
	_run: Callable[[sublime.Edit], None] | None = None

	def run(self, edit: sublime.Edit): #type: ignore
		run = DebuggerAsyncTextCommand._run
		DebuggerAsyncTextCommand._run = None
		if run: run(edit)
