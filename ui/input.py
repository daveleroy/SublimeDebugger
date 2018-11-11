
from sublime_db.core.typecheck import (
	Callable,
	Optional,
	Dict
)

import sublime

from .component import Component, ComponentInline, components
from .layout import Layout
from .button import Button
from .segment import Box
from .label import Label


class InputHandler:
	def __init__(self, window: sublime.Window, label: str, hint: str, on_change: Callable[[str], None],  on_done: Callable[[Optional[str]], None]):
		assert False, 'unimplemented'
	def close(self) -> None:
		assert False, 'unimplemented'

_create_input_handlers_for_window = {} #type: Dict[int, Callable[[sublime.Window,str,str,Callable[[str], None], Callable[[Optional[str]], None]], InputHandler]]

def set_create_input_handler(window: sublime.Window, create: Callable[[sublime.Window, str, str, Callable[[str], None], Callable[[Optional[str]], None]], InputHandler]) -> None:
	global _create_input_handlers_for_window
	_create_input_handlers_for_window[window.id()] = create

def create_input_handler_for_window(window: sublime.Window, label: str, hint: str, on_change: Callable[[str], None],  on_done: Callable[[Optional[str]], None]) -> InputHandler:
	create = _create_input_handlers_for_window.get(window.id())
	if create:
		return create(window, label, hint, on_change, on_done)
	return DefaultInputHandler(window, label, hint, on_change, on_done)
	
# class InputHandler:
# 	def get_input(on_change: Callable[[str], None], on_done: Callable[[str], None], on_cancel: Callable[[], None]) -> None
# 		assert False, 'unimplemented'

class DefaultInputHandler (InputHandler):
	def __init__(self, window: sublime.Window, label: str, hint: str, on_change: Callable[[str], None],  on_done: Callable[[Optional[str]], None]):
		def on_cancel() ->None:
			self.close()
			on_done(None)
		def on_done_inner(value: str) ->None:
			self.close()
			on_done(value)

		self.window = window
		self.active_panel = window.active_panel()
		window.show_input_panel(label, hint, on_done = on_done_inner, on_change = on_change, on_cancel = on_cancel)

	def close(self) -> None:
		self.window.run_command('show_panel', {
			'panel': '{}'.format(self.active_panel)
		})

# def add_input_handler(window: sublime.Window, input_handler: InputHandler)
# 	_input_handlers_for_window[window.id()] = input_handler

class Input(ComponentInline):

	def __init__(self, text: str, hint: str, on_done: Callable[[str], bool], width: int = 20) -> None:
		super().__init__()
		self.text = text
		self.hint = hint
		self.done = on_done
		self.width = width
		self.editing = False
		self.error = False
		self.input_handler = None #type: Optional[InputHandler]
	def on_focus(self) -> None:
		self.editing = True
		self.dirty()

		window = sublime.active_window()
		self.active_panel = window.active_panel()
		self.window = window
		self.input_handler = create_input_handler_for_window(window, self.hint, self.text, on_done = self.on_done, on_change = self.on_change)

	def on_unfocus(self) -> None:
		self.editing = False
		self.dirty()
		input_handler = self.input_handler
		self.input_handler = None
		if input_handler: input_handler.close()

	def on_done(self, value: Optional[str]) -> None:
		assert self.layout
		self.layout.unfocus(self)
		if value:
			self.text = value
		if self.done:
			self.error = not self.done(self.text)
		self.dirty()

	def on_change(self, value: str) -> None:
		self.text = value
		self.error = False
		self.dirty()

	def on_click(self) -> None:
		assert self.layout
		self.layout.focus(self)

	def render (self) -> components:
		className = ''
		if self.editing:
			className = ('editing')

		if self.error:
			className += (' error')

		text = self.text
		color = 'primary'
		if not text:
			color = 'secondary'
			text = self.hint

		box = Box(items =  [
			Label(text, padding_left = 0.75, padding_right = 0.75,  width = self.width, align = 0, color = color),
		])
		box.add_class(className)
		return [ 
			Button(self.on_click, items = [
				box
			])
		]