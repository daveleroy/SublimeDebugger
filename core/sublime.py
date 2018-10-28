from sublime_db.core.typecheck import (
	Any, 
	TypeVar, 
	Generic, 
	Tuple,
	List,
	Callable,
	Optional
)

import sublime
import sublime_plugin

from sublime_db.libs import asyncio

from .core import main_loop, async, awaitable

@async
def sublime_open_file_async(window: sublime.Window, file: str, line: int) -> awaitable[sublime.View]:
	from sublime_db import ui
	view = window.open_file(file)	
	if view.is_loading():
		future = main_loop.create_future()

		# FIXME this is terrible
		handle = ui.Handle(ui.view_loaded, None) #type: ignore
		def loaded_view(v: sublime.View) -> None:
			if view == v:
				future.set_result(view)
				handle.dispose()
		handle.callback = loaded_view
		ui.view_loaded.add_handle(handle)
		yield from future

	assert not view.is_loading(), "?? why is this view still loading?"
	view.show(view.text_point(line, 0), True)
	return view
	

@async
def sublime_show_quick_panel_async(window: sublime.Window, items: List[str], selected_index: int) -> awaitable[int]:
	done = main_loop.create_future()
	window.show_quick_panel(items, lambda index: done.set_result(index), selected_index = selected_index)
	r = yield from done
	return r

@async
def sublime_show_input_panel_async(window: sublime.Window, caption: str, initial_text: str, on_change: Callable[[str], None]) -> awaitable[Optional[str]]:
	result = main_loop.create_future()
	def on_done(value: str) -> None:
		result.set_result(value)
	def on_cancel() -> None:
		result.set_result(None)
	window.show_input_panel(caption, initial_text, on_done, on_change, on_cancel)
	r = yield from result
	return r