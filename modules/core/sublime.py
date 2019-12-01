from ..typecheck import *

import sublime
import sublime_plugin

from ..libs import asyncio

from .core import call_soon_threadsafe, create_future, coroutine, awaitable
from .event import Handle

@coroutine
def sublime_open_file_async(window: sublime.Window, file: str, line: Optional[int] = None) -> awaitable[sublime.View]:
	view = window.open_file(file)
	yield from wait_for_view_to_load(view)
	if line is None:
		return view
	view.show(view.text_point(line, 0), True)
	return view


@coroutine
def wait_for_view_to_load(view: sublime.View):
	from .. import ui
	future_view = create_future()

	# Do this stuff on the main thread. Otherwise we end up with the issue that the view_loaded event could happen before we register the callback for it.
	# and we don't want to register for the callback beforehand because we may not need to...
	def on_sublime_main() -> None:
		if view.is_loading():
			# FIXME this is terrible
			handle = Handle(ui.view_loaded, None) #type: ignore

			# this is called on our main thread
			def loaded_view(v: sublime.View) -> None:
				if view.id() == v.id():
					future_view.set_result(view)
					handle.dispose()

			handle.callback = loaded_view
			ui.view_loaded.add_handle(handle)
		else:
			# still on sublimes main thread so we need to set the result on our main thread
			call_soon_threadsafe(future_view.set_result, view)

	sublime.set_timeout(on_sublime_main, 0)

	yield from future_view
