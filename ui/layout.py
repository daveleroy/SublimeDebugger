from debug.core.typecheck import (
	List,
	Optional,
	Callable,
	TYPE_CHECKING
)

if TYPE_CHECKING: from .component import Component

import sublime
import os

from debug import core


_all_css = ''

def import_css(file: str):
	f = open(file, 'r')
	global _all_css
	_all_css += f.read()
	f.close()

class Layout:
	def __init__(self, item: 'Component') -> None:
		assert item.layout == None, 'item is already added to a layout'
		self.on_click_handlers = [] #type: List[Callable]
		self.item = item
		self.add_component(item)
		self.focused = None #type: Optional['Component']
		self.requires_render = True
		self.css = _all_css

	def dirty(self) -> None:
		self.requires_render = True

	def remove_component(self, item: 'Component') -> None:
		if self.focused == item:
			print('unfocusing removed item')
			self.unfocus()
			
		for item in item.render_items:
			self.remove_component(item)

		item.removed()
		item.layout = None

	def add_component(self, item: 'Component') -> None:
		#assert not item.layout, 'This item already has a layout?'
		item.layout = self
		item.added(self)

	def focus(self, item: 'Component') -> None:
		if self.focused == item: return #already focused
		self.unfocus()
		self.focused = item
		item.on_focus()

	def unfocus(self, item: 'Component' = None) -> None:
		if not self.focused: return
		self.focused.on_unfocus()
		self.focused = None

	def render(self) -> bool:
		if not self.requires_render:
			return False

		self.on_click_handlers = [] #type: Callable[[], None]
		self.item.render_dirty(self)
		self.html = self.item.html(self)
		self.requires_render = False
		return True

	def dispose(self) -> None:
		for item in self.item.render_items:
			assert item.layout, 'render items should always have been added?'
			item.layout.remove_component(item)

		assert self.item.layout, 'disposed twice?'
		self.item.layout.remove_component(self.item)

	def em_width(self) -> float:
		assert False, 'not implemented'
	# internal functions
	def on_navigate(self, path: str) -> None:
		id = int(path)
		try:
			handler = self.on_click_handlers[id]
		except:
			assert False, 'You probably called register_on_click_handler outside html generation... TODO: this should be fixed.....'
		
		#ensure this gets dispatched on our main thread not sublime's
		core.main_loop.call_soon_threadsafe(handler)
	
	def register_on_click_handler(self, callback: 'Callable') -> str:
		id = len(self.on_click_handlers)
		self.on_click_handlers.append(callback)
		return str(id)


