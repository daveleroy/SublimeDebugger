from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Type, cast

from .. import core
from .css import css
from .html import HtmlResponse, div, element

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
	layouts_to_add: ClassVar[list[Layout]] = []
	layouts_to_remove: ClassVar[list[Layout]] = []
	layouts: ClassVar[list[Layout]] = []
	_render_scheduled = False

	on_layout_invalidated: Callable[[], None] | None = None

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
				status += f'{r.stats.name}: {len(r.html) / 1024:.1f}kb {r.stats.render_time:.1f}ms {r.stats.render_count}x'

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
		self.html = ''

		self.view = view

		self.luminocity = 0.0

		self.width = 0.0
		self.height = 0.0

		self.layout_width = 1.0
		self.layout_height = 1.0

		self.internal_font_scale = 1.0
		self.internal_width_modifier = 0.0

		self.font_size = 1.0
		self.em_width = 1.0

		self.scrolling = False
		self.viewport_bottom = 0
		self.viewport_position_depedent = False

		self._layout_values = ()
		self._layout_scrolling_values = ()
		self._scrolling_time = None
		self._vertical_offset = 0.0
		self._last_check_was_differnt = 0

		self._on_click_handlers: dict[int, Callable[[], None]] = {}
		self._on_click_handlers_id = 0

		self.item = div()
		self.item.layout = self

		self.update()
		Layout.layouts_to_add.append(self)

	def __str__(self):
		return f'Layout: {self.stats.name}'

	@staticmethod
	def layout_at_layout_position(view: sublime.View, layout_position: tuple[float, float]):
		found_layout = None
		for layout in Layout.layouts:
			print(layout)
			if layout.view == view and layout.inside_region(layout_position[0]):
				found_layout = layout
				break
		return found_layout

	# FIX: This doesn't really fully implement what is required.
	# It only looks at where the item would be rendered verticaly and doesn't take into account the actual width/height
	def element_at_layout_position(self, layout_position: tuple[float, float], type: Type | None):
		target_position_y = self.from_dip(layout_position[1])
		found: Any = None

		def visit(item: div, position_y: float):
			nonlocal found

			# we are currently only looking at the vertical position we would need to know the available width otherwise
			if item.children_rendered_inline:
				return item.html_height(10000, 10000)

			target_height = target_position_y - position_y
			height = 0
			for child in item.children_rendered:
				child = cast(div, child)
				height_before = height
				height += visit(child, position_y + height)

				# check if this element was is at the position
				if height_before < target_height and height > target_height:
					if not type or isinstance(child, type):
						found = found or child

			return height + item.css_padding_height

		visit(self.item, 0)
		return found

	def dispose(self) -> None:
		Layout.layouts_to_remove.append(self)

	def inside_region(self, position_x: float) -> bool:
		return True

	def __enter__(self):
		self.item.__enter__()
		return self

	def __exit__(self, *args):
		self.item.__exit__()

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
			child.layout = None  # type: ignore

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
		html = ['<style>', css_string, '</style>', f'<body id="debugger" style="padding-top: {self.vertical_offset}px;">', self.item.html(25, 10000), '</body>']

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
		self.invalidate_layout_if_needed()

		if self.viewport_position_depedent:
			self.invalidate_viewport_position_if_needed()

	def invalidate_viewport_position_if_needed(self):
		viewport_position_y = self.view.viewport_position()[1]
		viewport_height = self.view.viewport_extent()[1]

		scolling = self._layout_scrolling_values and abs(viewport_position_y - self._layout_scrolling_values[0]) > 1
		if scolling and not self.scrolling:
			if self._scrolling_time:
				self._scrolling_time.cancel()
				self._scrolling_time = None

			self.scrolling = True
			self.invalidate()

		values = (
			viewport_position_y,
			viewport_height,
		)
		self._layout_scrolling_values = values

		if self.scrolling and not scolling and not self._scrolling_time:

			def finished():
				self.scrolling = False
				self.invalidate()

			self._scrolling_time = core.call_later(0.25, finished)

		self.viewport_bottom = (viewport_height + viewport_position_y) / self.em_width

	def invalidate_layout_if_needed(self):
		style = self.view.style()
		background = style.get('background') if style else None

		settings = self.view.settings()
		font_size = settings.get('font_size') or 12

		internal_font_scale = settings.get('internal_font_scale', 1)
		internal_width_modifier = settings.get('internal_width_modifier', 0)

		viewport_width, viewport_height = self.view.viewport_extent()
		layout_width, _ = self.view.layout_extent()

		em_width = self.view.em_width() or 1

		# check if anything has changed so we can avoid invalidating the layout
		layout_values = (background, font_size, internal_font_scale, internal_width_modifier, em_width, viewport_width, viewport_height, layout_width)

		if self._layout_values == layout_values:
			# only invalidate the layout after the user has stopped changing the layout to avoid redrawing while they are changing stuff
			if self._last_check_was_differnt == 0:
				self.invalidate()

			self._last_check_was_differnt -= 1
			return

		self._layout_values = layout_values

		self.layout_width = layout_width / em_width

		self.internal_font_scale = internal_font_scale
		self.internal_width_modifier = internal_width_modifier

		self.font_size = font_size
		self.width = viewport_width / em_width
		self.luminocity = lightness_from_color(background)
		self.em_width = em_width

		self._last_check_was_differnt = 5


def lightness_from_color(color: str | None) -> float:
	if not color:
		return 0
	color = color.lstrip('#')
	rgb = tuple(int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
	lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
	return lum
