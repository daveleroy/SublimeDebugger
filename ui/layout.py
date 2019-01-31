from sublime_db.core.typecheck import (
	List,
	Optional,
	Callable,
	Dict,
	TYPE_CHECKING
)

if TYPE_CHECKING: from .component import Component

import sublime
import os

from sublime_db import core
from . import size

_all_css = size.css()
_css_files = [] #type: List[str]
def import_css(file: str) -> None:
	_css_files.append(file)
	_add_css_from_file(file)

def _add_css_from_file(file: str) -> None:
	f = open(file, 'r')
	global _all_css
	_all_css += f.read()
	f.close()

def reload_css() -> None:
	_all_css = size.css()
	for file in _css_files:
		_add_css_from_file(file)

class Layout:
	def __init__(self, item: 'Component') -> None:
		assert item.layout == None, 'item is already added to a layout'
		self.on_click_handlers = {} #type: Dict[int, Callable]
		self.on_click_handlers_id = 0
		self.item = item
		self.add_component(item)
		self.focused = None #type: Optional['Component']
		self.requires_render = True
		self.css = _all_css
		
	def dirty(self) -> None:
		self.requires_render = True

	def remove_component_children(self, item: 'Component') -> None:
		for inner_item in item.render_items:
			assert inner_item.layout
			inner_item.layout.remove_component(inner_item)
			
		item.render_items = []

	def remove_component(self, item: 'Component') -> None:
		if self.focused == item:
			print('unfocusing removed item')
			self.unfocus(item)
			
		self.remove_component_children(item)

		item.removed()
		item.layout = None
		
	def add_component_children(self, item: 'Component') -> None:
		for item in item.render_items:
			self.add_component(item)

	def add_component(self, item: 'Component') -> None:
		assert not item.layout, 'This item already has a layout?'
		item.layout = self
		item.added(self)

	def focus(self, item: 'Component') -> None:
		if self.focused == item: return #already focused
		if self.focused:
			self.unfocus(self.focused)
		self.focused = item
		item.on_focus()

	def unfocus(self, item: 'Component') -> None:
		if not self.focused: return
		if self.focused != item: return
		self.focused.on_unfocus()
		self.focused = None

	def render(self) -> bool:
		if not self.requires_render:
			return False

		self.on_click_handlers = {}
		self.item.render_dirty(self)
		self.html = self.item.html(self)
		self.requires_render = False
		return True

	def dispose(self) -> None:
		self.remove_component(self.item)

	def em_width(self) -> float:
		assert False, 'not implemented'

	# internal functions
	@core.async
	def on_navigate_main(self, path: str) -> core.awaitable[None]:
		id = int(path)
		if id in self.on_click_handlers:
    			self.on_click_handlers[id]()

	def on_navigate(self, path: str) -> None:
		#ensure this gets dispatched on our main thread not sublime's
		core.run(self.on_navigate_main(path))
	
	def register_on_click_handler(self, callback: 'Callable') -> str:
		self.on_click_handlers_id += 1
		id = self.on_click_handlers_id
		self.on_click_handlers[id] = callback
		return str(id)


