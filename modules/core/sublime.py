from __future__ import annotations
from re import sub
from typing import Any, Callable, Protocol, TypeVar
from .typing_extensions import TypeVarTuple, Unpack, Concatenate, ParamSpec

from functools import wraps

import sublime
import sublime_plugin

from .asyncio import Future
from .event import Event


async def sublime_open_file_async(window: sublime.Window, file: str, line: int | None = None, column: int | None = None, group: int = -1) -> sublime.View:
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


def window_from_view_or_widow(view_or_window: sublime.View | sublime.Window):
	if isinstance(view_or_window, sublime.View):
		return view_or_window.window()
	return view_or_window


T = TypeVar('T')

Args = TypeVarTuple('Args')
Params = ParamSpec('Params')


def edit(view: sublime.View, run: Callable[[sublime.Edit], Any]):
	previous = DebuggerEditCommand._run
	DebuggerEditCommand._run = run
	view.run_command('debugger_edit')
	DebuggerEditCommand._run = previous


def sublime_edit(value: Callable[Concatenate[sublime.View, sublime.Edit, Params], T]) -> Callable[Concatenate[sublime.View, Params], T]:
	@wraps(value)
	def wrap(view: sublime.View, *args, **kwargs):
		return edit(view, lambda edit: value(view, edit, *args, **kwargs))

	return wrap  # type: ignore


class Viewable(Protocol):
	@property
	def view(self) -> sublime.View: ...


SelfViewable = TypeVar('SelfViewable', bound=Viewable)


def sublime_edit_method(value: Callable[Concatenate[SelfViewable, sublime.Edit, Params], T]) -> Callable[Concatenate[SelfViewable, Params], T]:
	@wraps(value)
	def wrap(self: SelfViewable, *args, **kwargs):
		return edit(self.view, lambda edit: value(self, edit, *args, **kwargs))

	return wrap  # type: ignore


on_view_load: Event[sublime.View] = Event()


class DebuggerEditCommand(sublime_plugin.TextCommand):
	_run: Callable[[sublime.Edit], None] | None = None

	def run(self, edit: sublime.Edit):
		if run := DebuggerEditCommand._run:
			DebuggerEditCommand._run = None
			run(edit)
