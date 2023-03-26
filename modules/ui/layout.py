from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, ClassVar

from ..import core
from .style import css
from .html import HtmlResponse, div, element
from collections.abc import Iterable
import sublime

def flatten_element_children(items: element.Children, list: list[element]):
	if items is None:
		pass
	elif isinstance(items, Iterable):
		for item in items:
			flatten_element_children(item, list)
	else:
		list.append(items)


def flatten_html_response(items: HtmlResponse, list: list[str]):
	if type(items) is str:
		list.append(items)
		return

	for item in items:
		flatten_html_response(item, list)

@dataclass
class LayoutStats:
	name: str

	render_count: int = 0
	render_element_count: int = 0

	render_time: float = 0
	render_time_total: float = 0

class Layout:
	layouts_to_add:ClassVar[list[Layout]] = []
	layouts_to_remove: ClassVar[list[Layout]] = []
	layouts: ClassVar[list[Layout]] = []
	_render_scheduled = False

	debug: bool = False

	@staticmethod
	def update_layouts():
		for l in Layout.layouts:
			l.update()

		if Layout.debug:
			Layout.render_debug_info()

	@staticmethod
	def render_debug_info():
		status = ''
		for r in Layout.layouts:
			status += '         '
			status += f'{r.stats.name}: {len(r.html)/1024:.1f}kb {r.stats.render_time:.1f}ms {r.stats.render_count}x'

		sublime.active_window().status_message(status)

	@staticmethod
	def render_layouts():
		Layout._render_scheduled = False

		Layout.layouts.extend(Layout.layouts_to_add)
		Layout.layouts_to_add.clear()

		for r in Layout.layouts_to_remove:
			try:
				Layout.layouts.remove(r)
			except ValueError:
				...

		Layout.layouts_to_remove.clear()

		for r in Layout.layouts:
			r.render()

		if Layout.debug:
			Layout.render_debug_info()


	@staticmethod
	def _schedule_render_layouts() -> None:
		if Layout._render_scheduled:
			return

		Layout._render_scheduled = True
		core.call_soon(Layout.render_layouts)

	def __init__(self, view: sublime.View) -> None:
		self.stats = LayoutStats(name=view.name())

		self.on_click_handlers: dict[int, Callable[[], None]] = {}
		self.on_click_handlers_id = 0
		self.requires_render = True
		self.html_list: list[str] = []
		self.html = ""

		self.view = view
		self._width = 0.0
		self._height = 0.0
		self._lightness = 0.0

		self._all = ()
		self._vertical_offset = 0.0
		self._last_check_was_differnt = False

		self.item = div()
		self._add_element(self.item)

		self.update()
		Layout.layouts_to_add.append(self)

	def dispose(self) -> None:
		self._remove_element(self.item)
		Layout.layouts_to_remove.append(self)

	def __getitem__(self, values: div.Children):
		self.item [
			values
		]
		self._add_element(self.item)
		self.dirty()
		return self

	@property
	def vertical_offset(self):
		return self._vertical_offset

	@vertical_offset.setter
	def vertical_offset(self, value: float):
		if self._vertical_offset != value:
			self._vertical_offset = value
			self.dirty()

	# from sublime dip units to character width units
	def from_dip(self, dip: float) -> float:
		return dip / self.em_width

	def dirty(self) -> None:
		self.requires_render = True
		Layout._schedule_render_layouts()

	def _add_element_children(self, parent: element) -> None:
		if parent.is_inline:
			for child in parent.children:
				self._add_element(child)
		else:
			if parent.width is not None:
				available_block_width = parent.width
			else:
				available_block_width = parent._available_block_width and parent._available_block_width - parent.css_padding_width

			for child in parent.children:
				child._available_block_width = available_block_width
				self._add_element(child)

	def _add_element(self, item: element) -> None:
		assert not item.layout, 'This item already has a layout?'
		item.layout = self
		item.added()

	def _remove_element(self, item: element) -> None:
		self._remove_element_children(item)
		item.removed()
		item.layout = None #type: ignore

	def _remove_element_children(self, item: element) -> None:
		for child in item.children:
			self._remove_element(child)

		item.children = []

	def render_element_tree(self, item: element, requires_render: bool = False) -> None:
		if not requires_render and not item.requires_render:

			# check the children elements
			for child in item.children:
				self.render_element_tree(child)
			return

		item.requires_render = False

		# remove old and add new
		self._remove_element_children(item)
		item.children.clear()
		flatten_element_children(item.render(), item.children)
		self._add_element_children(item)

		# all the children must be rendered since the parent required rendering
		for child in item.children:
			self.render_element_tree(child, True)

	def render(self) -> bool:
		if not self.requires_render:
			return False

		self.on_click_handlers.clear()
		self.requires_render = False
		self.render_element_tree(self.item)

		css_string = css.generate(self)
		html = [
			f'<body id="debugger" style="padding-top: {self.vertical_offset}px;">',
				'<style>',
					css_string,
				'</style>',
				self.item.html(),
			'</body>'
		]

		self.html_list.clear()
		flatten_html_response(html, self.html_list)
		self.html = ''.join(self.html_list)
		return True

	def on_navigate(self, path: str) -> None:
		id = int(path)
		if id in self.on_click_handlers:
			self.on_click_handlers[id]()

	def register_on_click_handler(self, callback: Callable[[], None]) -> str:
		self.on_click_handlers_id += 1
		id = self.on_click_handlers_id
		self.on_click_handlers[id] = callback
		return str(id)

	# width/height of the viewport in character width units
	# for instance 6.5 is equal to 6 and 1/2 characters
	def width(self) -> float:
		return self._width

	def height(self) -> float:
		return self._height

	def luminocity(self) -> float:
		return self._lightness

	def update(self) -> None:
		style = self.view.style()
		background = style.get('background') if style else None

		settings = self.view.settings()
		font_size = settings.get('font_size') or 1

		width, height = self.view.viewport_extent()
		em_width = self.view.em_width() or 1

		# check if anything has changed so we can avoid invalidating the layout
		all = (background, font_size, em_width, width, height)
		if self._all == all:

			# only invalidate the layout after the user has stopped changing the layout to avoid redrawing while they are changing stuff
			if self._last_check_was_differnt:
				self._last_check_was_differnt = False
				self.item.dirty()

			return

		self._all = all

		self.font_size = font_size
		self._width = width / em_width
		self._height = height / em_width
		self._lightness = lightness_from_color(background)
		self.em_width = em_width

		self._last_check_was_differnt = True


def lightness_from_color(color: str|None) -> float:
	if not color:
		return 0
	color = color.lstrip('#')
	rgb = tuple(int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
	lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
	return lum
