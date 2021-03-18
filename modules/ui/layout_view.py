from __future__ import annotations
from ..typecheck import *

from ..import core
from . html import div, span, phantom_sizer, element
from . layout import Layout
from . style import css
from . image import view_background_lightness

import os
import sublime


class LayoutComponent (Layout):
	def __init__(self, item: Union[div, span]) -> None:
		assert item.layout is None, 'item is already added to a layout'
		self.on_click_handlers = {} #type: Dict[int, Callable]
		self.on_click_handlers_id = 0
		self.requires_render = True
		self._font_size = 12

		self.item = phantom_sizer(div()[item])
		self.add_component(self.item)
		self.dirty()

	def __getitem__(self, values: 'div.Children'):
		if isinstance(values, element):
			self.item = phantom_sizer(div()[values])
		else:
			self.item = phantom_sizer(div()[values])

		self.add_component(self.item)
		self.dirty()
		return self

	def dirty(self) -> None:
		from .render import schedule_render
		self.requires_render = True
		schedule_render()

	def remove_component_children(self, item: element) -> None:
		for child in item.children:
			assert child.layout
			child.layout.remove_component(child)

		item.children = []

	def remove_component(self, item: element) -> None:
		self.remove_component_children(item)
		item.removed()
		item.layout = None

	def add_component_children(self, item: element) -> None:
		if item._width is not None:
			_parent_width = item._width
		else:
			_parent_width = item._max_allowed_width and item._max_allowed_width - item.padding_width

		for item in item.children:
			item._max_allowed_width = _parent_width
			self.add_component(item)

	def add_component(self, item: element) -> None:
		assert not item.layout, 'This item already has a layout?'
		item.layout = self
		item.added(self)

	def render_component_tree(self, item: element) -> None:
		item.requires_render = False
		self.remove_component_children(item)
		children = item.render()

		if children is None:
			item.children = []
		elif isinstance(children, element):
			item.children = (children, )
		else:
			item.children = children

		self.add_component_children(item)

		for child in item.children:
			self.render_component_tree(child)

	def render_component(self, item: element) -> None:
		if item.requires_render:
			self.render_component_tree(item)
		else:
			for child in item.children:
				self.render_component(child)

	def render(self) -> bool:
		if not self.requires_render:
			return False

		self.on_click_handlers.clear()
		self.requires_render = False

		if self.item:
			self.render_component(self.item)
			self.html = f'''<body id="debug"><style>html{{font-size:{self._font_size}px}}{css.all}</style>{self.item.html(self)}</body>'''
		else:
			self.html = ""

		return True

	def dispose(self) -> None:
		self.remove_component(self.item)

	def on_navigate(self, path: str) -> None:
		id = int(path)
		if id in self.on_click_handlers:
			self.on_click_handlers[id]()

	def register_on_click_handler(self, callback: 'Callable') -> str:
		self.on_click_handlers_id += 1
		id = self.on_click_handlers_id
		self.on_click_handlers[id] = callback
		return str(id)


class LayoutView (LayoutComponent):
	def __init__(self, item: Union[div, span], view: sublime.View) -> None:
		super().__init__(item)
		self.view = view
		self._width = 0.0
		self._height = 0.0
		self._lightness = 0.0
		self._rem_width_scale = 0.0
		self.update()

	def width(self) -> float:
		return self._width

	def height(self) -> float:
		return self._height

	def luminocity(self) -> float:
		return self._lightness

	def rem_width_scale(self):
		return self._rem_width_scale

	def update(self) -> None:
		lightness = view_background_lightness(self.view)
		em_width = (self.view.em_width() or 7)

		# why is this calculation off on windows?
		# hard code a reasonable (but low) approximation
		# something is wrong but I do not know what? Or maybe there is a bug with the viewport_extent/rem_width/font_size in output panels on windows?
		# calculating the width of the viewport above still works on windows...
		if core.platform.windows:
			font_size = em_width / 0.55
		elif core.platform.linux:
			font_size = em_width / 0.625
		else:
			font_size = self.view.settings().get('font_size') or 12

		rem_width_scale = em_width/font_size


		size = self.view.viewport_extent()
		width = size[0] / em_width
		height = size[1] / em_width

		if self._width != width or self._height != height or self._lightness != lightness or self._rem_width_scale != rem_width_scale:
			self._font_size = font_size
			self._width = width
			self._height = height
			self._lightness = lightness
			self._rem_width_scale = rem_width_scale
			self.item.dirty()

	def force_dirty(self) -> None:
		self.item.dirty()
