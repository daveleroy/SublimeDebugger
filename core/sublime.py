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
from .event import Handle

@async
def sublime_open_file_async(window: sublime.Window, file: str, line: Optional[int] = None) -> awaitable[sublime.View]:
	from sublime_db import ui
	future_view = main_loop.create_future()

	# Do this stuff on the main thread. Otherwise we end up with the issue that the view_loaded event could happen before we register the callback for it.
	# and we don't want to register for the callback beforehand because we may not need to...
	def on_sublime_main() -> None:
		view = window.open_file(file)
		if view.is_loading():
			# FIXME this is terrible
			handle = Handle(ui.view_loaded, None) #type: ignore
			def loaded_view(v: sublime.View) -> None:
				if view.id() == v.id():
					future_view.set_result(view)
					handle.dispose()
			handle.callback = loaded_view
			ui.view_loaded.add_handle(handle)
		else:
			future_view.set_result(view)

	sublime.set_timeout(on_sublime_main, 0)

	view = yield from future_view
	assert not view.is_loading(), "?? why is this view still loading?"

	if line is None:
		return view
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