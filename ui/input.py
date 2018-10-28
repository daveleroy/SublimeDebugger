
from sublime_db.core.typecheck import (
	Callable,
	Optional
)

import sublime

from .component import Component, ComponentInline, components
from .layout import Layout
from .button import Button
from .segment import Box
from .label import Label

class Input(ComponentInline):

	def __init__(self, text: str, hint: str, on_done: Callable[[str], bool], width: int = 20) -> None:
		super().__init__()
		self.text = text
		self.hint = hint
		self.done = on_done
		self.width = width
		self.editing = False
		self.error = False

	def on_focus(self) -> None:
		self.editing = True
		self.dirty()

		window = sublime.active_window()
		self.active_panel = window.active_panel()
		self.window = window
		window.show_input_panel(self.hint, self.text, on_done = self.on_done, on_change = self.on_change, on_cancel = self.on_cancel)

	def on_unfocus(self) -> None:
		self.editing = False
		self.dirty()

		if self.active_panel:
			print('restoring panel', self.active_panel)
			self.window.run_command('show_panel', {
				'panel': '{}'.format(self.active_panel)
			})

	def on_done(self, value: str) -> None:
		assert self.layout
		self.layout.unfocus(self)
		if self.done:
			self.error = not self.done(value)
		self.dirty()

	def on_change(self, value: str) -> None:
		self.text = value
		self.error = False
		self.dirty()

	def on_cancel(self) -> None:
		if self.layout:
			self.layout.unfocus(self)	

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