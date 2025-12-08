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
class Stats:
	name: str

	render_count: int = 0
	render_element_count: int = 0

	render_time: float = 0
	render_time_total: float = 0


class ViewRegistry:
	layouts_to_add: ClassVar[list[View]] = []
	layouts_to_remove: ClassVar[list[View]] = []
	layouts: ClassVar[list[View]] = []
	render_scheduled = False
	debug = False

	@staticmethod
	def register(view: View):
		ViewRegistry.layouts_to_add.append(view)

	@staticmethod
	def unregister(view: View):
		ViewRegistry.layouts_to_remove.append(view)

	@staticmethod
	def update_layouts():
		for l in ViewRegistry.layouts:
			l.update()

		if ViewRegistry.debug:
			ViewRegistry.render_debug_info()

	@staticmethod
	def render_debug_info():
		status = ''
		for r in ViewRegistry.layouts:
			if r.view.window() == sublime.active_window():
				status += '         '
				status += f'{r.stats.name}: {len(r.html) / 1024:.1f}kb {r.stats.render_time:.1f}ms {r.stats.render_count}x'

		sublime.active_window().status_message(status)

	@staticmethod
	def render_layouts():
		ViewRegistry.render_scheduled = False

		ViewRegistry.layouts.extend(ViewRegistry.layouts_to_add)
		ViewRegistry.layouts_to_add.clear()

		for r in ViewRegistry.layouts_to_remove:
			try:
				ViewRegistry.layouts.remove(r)
			except ValueError:
				...

		ViewRegistry.layouts_to_remove.clear()

		for r in ViewRegistry.layouts:
			r.render()

		if ViewRegistry.debug:
			ViewRegistry.render_debug_info()

	@staticmethod
	def invalidated_view(view: View) -> None:
		if ViewRegistry.render_scheduled:
			return

		ViewRegistry.render_scheduled = True
		core.call_soon(ViewRegistry.render_layouts)

	@staticmethod
	def view_at_position(view: sublime.View, layout_position: tuple[float, float]):
		found_layout = None
		for layout in ViewRegistry.layouts:
			if layout.view == view and layout.inside_region(layout_position[0]):
				found_layout = layout
				break
		return found_layout


class View:
	def __init__(self, view: sublime.View) -> None:
		self.stats = Stats(name=view.name())

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

		self._layout_values = ()
		self._last_check_was_differnt = 0

		self._on_click_handlers: dict[int, Callable[[], None]] = {}
		self._on_click_handlers_id = 0

		self.item = div()
		self.item.layout = self

		self.update()

		ViewRegistry.register(self)

	def __str__(self):
		return f'Layout: {self.stats.name}'

	# FIX: This doesn't really fully implement what is required.
	# It only looks at where the item would be rendered verticaly and doesn't take into account the actual width/height
	def element_at_layout_position(self, layout_position: tuple[float, float], type: Type | None) -> element | None:
		target_position_y = self.from_dip(layout_position[1])
		found: element|None = None

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
		ViewRegistry.unregister(self)

	def inside_region(self, position_x: float) -> bool:
		return True

	def __enter__(self):
		self.item.__enter__()
		return self

	def __exit__(self, *args):
		self.item.__exit__()

	# from sublime dip units to character width units
	def from_dip(self, dip: float) -> float:
		return dip / self.em_width

	def invalidate(self) -> None:
		self.item.dirty()
		self.requires_render = True
		ViewRegistry.invalidated_view(self)

	def dirty(self) -> None:
		self.requires_render = True
		ViewRegistry.invalidated_view(self)

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
		html = ['<style>', css_string, '</style>', '<body id="debugger">', self.item.html(25, 10000), '</body>']

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
