from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, ClassVar

from ..import core
from .css import css
from .html import HtmlResponse, div, element, enter_render_frame, exit_render_frame

import sublime

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

	on_layout_invalidated: Callable[[], None]|None = None

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
			if r.view.window() == sublime.active_window():
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


		self.requires_render = True
		self.html_list: list[str] = []
		self.html = ""

		self.view = view

		self.luminocity = 0.0
		self.viewport_position_y = 0

		self.width = 0.0
		self.height = 0.0

		self.layout_width = 1.0
		self.layout_height = 1.0

		self.internal_font_scale = 1.0
		self.internal_width_modifier = 0.0

		self.font_size = 1.0
		self.em_width = 1.0

		self._all = ()
		self._vertical_offset = 0.0
		self._last_check_was_differnt = 0
		self.scrolling = False

		self._on_click_handlers: dict[int, Callable[[], None]] = {}
		self._on_click_handlers_id = 0

		self.item = div()
		self.item.layout = self

		self.update()
		Layout.layouts_to_add.append(self)


	def dispose(self) -> None:
		Layout.layouts_to_remove.append(self)

	def __enter__(self):
		enter_render_frame()
		return self

	def __exit__(self, *args):
		items = exit_render_frame()
		self.item.assign_children(items)
		self.dirty()

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

	def invalidate(self) -> None:
		self.item.dirty()
		self.requires_render = True
		Layout._schedule_render_layouts()

		if self.on_layout_invalidated:
			self.on_layout_invalidated()

	def dirty(self) -> None:
		self.requires_render = True
		Layout._schedule_render_layouts()

	def _add_element_children(self, parent: element) -> None:
		for child in parent.children_rendered:
			assert not child.layout, 'This item already has a layout?'
			child.layout = self
			child.added()

	def _remove_element_children(self, parent: element) -> None:
		for child in parent.children_rendered:
			self._remove_element_children(child)
			child.removed()
			child.layout = None #type: ignore


	def render_element_tree(self, item: element, requires_render: bool = False) -> None:
		if not requires_render and not item.requires_render:
			# check the children elements
			for child in item.children_rendered:
				self.render_element_tree(child)
			return

		item.requires_render = False

		# remove old and add new
		self._remove_element_children(item)
		item.perform_render()
		self._add_element_children(item)

		# all the children must be rendered since the parent required rendering
		for child in item.children_rendered:
			self.render_element_tree(child, True)

	def render(self) -> bool:
		if not self.requires_render:
			return False

		self._on_click_handlers.clear()
		self.requires_render = False

		self.render_element_tree(self.item)

		css_string = css.generate(self)
		html = [
			'<style>',
				css_string,
			'</style>',
			f'<body id="debugger" style="padding-top: {self.vertical_offset}px;">',
				self.item.html(25, 10000),
			'</body>'
		]

		self.html_list.clear()
		flatten_html_response(html, self.html_list)
		self.html = ''.join(self.html_list)
		return True

	def on_navigate(self, path: str) -> None:
		id = int(path)
		if id in self._on_click_handlers:
			self._on_click_handlers[id]()

	def register_on_click_handler(self, callback: Callable[[], None]) -> str:
		self._on_click_handlers_id += 1
		id = self._on_click_handlers_id
		self._on_click_handlers[id] = callback
		return str(id)

	def update(self) -> None:
		style = self.view.style()
		background = style.get('background') if style else None

		settings = self.view.settings()
		font_size = settings.get('font_size', 12)

		internal_font_scale = settings.get('internal_font_scale', 1)
		internal_width_modifier = settings.get('internal_width_modifier', 0)

		viewport_width, viewport_height = self.view.viewport_extent()
		layout_width, layout_height = self.view.layout_extent()

		viewport_position_x, viewport_position_y = self.view.viewport_position()
		em_width = self.view.em_width() or 1

		scolling = abs(viewport_position_y / em_width - self.viewport_position_y) > 0.05
		if scolling and not self.scrolling:
			self.scrolling = True
			self.invalidate()

		# check if anything has changed so we can avoid invalidating the layout
		all = (
			background,
			font_size,
			internal_font_scale,
			internal_width_modifier,
			em_width,
			viewport_width,
			viewport_height,
			viewport_position_x, viewport_position_y,
			layout_height,
			layout_width
		)

		if self._all == all:
			# only invalidate the layout after the user has stopped changing the layout to avoid redrawing while they are changing stuff
			if self._last_check_was_differnt == 0:
				self.invalidate()

			if self._last_check_was_differnt == -2 and self.scrolling and not scolling:
				self.scrolling = False
				self.invalidate()

			self._last_check_was_differnt -= 1
			return

		self._all = all
		self.layout_width = layout_width / em_width
		self.layout_height = layout_height / em_width
		self.viewport_position_y = viewport_position_y / em_width

		self.internal_font_scale = internal_font_scale
		self.internal_width_modifier = internal_width_modifier

		self.font_size = font_size
		self.width = viewport_width / em_width
		self.height = viewport_height / em_width
		self.luminocity = lightness_from_color(background)
		self.em_width = em_width

		self._last_check_was_differnt = 5

def lightness_from_color(color: str|None) -> float:
	if not color:
		return 0
	color = color.lstrip('#')
	rgb = tuple(int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
	lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
	return lum
