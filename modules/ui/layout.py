from __future__ import annotations

from ..typecheck import *

from ..import core
from .style import css
from .html import div, span, element
from .debug import DEBUG_TIMING, DEBUG_TIMING_STATUS

import sublime

def flatten_without_none(items: element.Children) -> Generator[element, None, None]:

	if items is None: pass
	elif isinstance(items, element):
		yield items
	else:
		for item in items:
			yield from flatten_without_none(item)


class Layout:
	layouts_to_add:ClassVar[list[Layout]] = []
	layouts_to_remove: ClassVar[list[Layout]] = []
	layouts: ClassVar[list[Layout]] = []
	_render_scheduled = False

	@staticmethod
	def update_layouts():
		for l in Layout.layouts:
			l.update()

	@staticmethod
	def render_layouts():
		Layout._render_scheduled = False

		Layout.layouts.extend(Layout.layouts_to_add)
		Layout.layouts_to_add.clear()

		for r in Layout.layouts_to_remove:
			Layout.layouts.remove(r)

		Layout.layouts_to_remove.clear()

		status = ' | '

		if DEBUG_TIMING: print('-------------------------')

		for r in Layout.layouts:
			if DEBUG_TIMING: print('-------------------------')
			stopwatch = core.stopwatch('total')
			r.render()
			if DEBUG_TIMING:  stopwatch.print()

			status += f'{r.last_render_time:.2f} | '

		if DEBUG_TIMING_STATUS: sublime.active_window().status_message(status)

	@staticmethod
	def _schedule_render_layouts() -> None:
		if Layout._render_scheduled:
			return

		Layout._render_scheduled = True
		core.call_soon(Layout.render_layouts)

	

	count: dict[str, int] = {}

	# from sublime dip units to character width units
	def from_dip(self, dip: float) -> float:
		return dip / self._em_width

	# from characters to rem units which are used in html/css
	def to_rem(self, character_widths: float) -> float:
		return self._em_width_to_rem * character_widths

	def __init__(self, view: sublime.View) -> None:
		self.on_click_handlers: dict[int, Callable[[], None]] = {}
		self.on_click_handlers_id = 0
		self.requires_render = True
		self.html = ""
		self.item: div|None = None
		self.view = view
		self._width = 0.0
		self._height = 0.0
		self._lightness = 0.0
		self.last_render_time = 0
		self._all = ()
		self.update()
		Layout.layouts_to_add.append(self)

	def dispose(self) -> None:
		if self.item:
			self.remove_component(self.item)
		Layout.layouts_to_remove.append(self)

	def __getitem__(self, values: div.Children):
		self.item = div()[values]
		self.add_component(self.item)
		self.dirty()
		return self

	def dirty(self) -> None:
		self.requires_render = True
		Layout._schedule_render_layouts()

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

	def remove_component(self, item: element) -> None:
		self.remove_component_children(item)
		item.removed()
		item.layout = None

	def remove_component_children(self, item: element) -> None:
		for child in item.children:
			assert child.layout
			child.layout.remove_component(child)

		item.children = []


	def render_component_tree(self, item: element|None) -> None:
		if item is None:
			return

		item.requires_render = False
		self.remove_component_children(item)

		key = type(item).__name__
		self.count[key] = self.count.get(key, 0) + 1

		children = item.render()
		item.children = list(flatten_without_none(children))

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

		if not self.item:
			return False

		self.on_click_handlers.clear()
		self.requires_render = False

		timer = core.stopwatch('render')
		self.render_component(self.item)
		if DEBUG_TIMING: timer()

		timer = core.stopwatch('css')
		css_string = css.generate(self)

		if DEBUG_TIMING:
			timer(f'{len(css_string)}')

		timer = core.stopwatch('html')
		html = f'<body id="debugger"><style>{css_string}</style>{self.item.html(self)}</body>'

		self.html = html

		if DEBUG_TIMING:
			timer(f'{len(self.html)}')


		self.count = {}
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
		if style := self.view.style():
			background = style.get('background')
		else:
			background = None

		size = self.view.viewport_extent()
		settings = self.view.settings()
		font_size = settings.get('font_size') or 1
		rem_width_scale = settings.get('rem_width_scale') or 1
		em_width = (self.view.em_width() or 1)
		# print(self.view.viewport_extent())
		# check if anything has changed so we can avoid invalidating the layout
		all = (background, font_size, rem_width_scale, em_width, size[0], size[1])
		# print(all, self._all, size)
		if self._all == all:
			return

		self._all = all

		self._width = size[0] / em_width
		self._height = size[1] / em_width
		self._lightness = lightness_from_color(background)

		# units in minihtml are based on the font_size of the character however we want our units to be 1 character wide
		self._em_width_to_rem = em_width / font_size *  rem_width_scale
		self._em_width = em_width

		if self.item:
			self.item.dirty()


def lightness_from_color(color: str|None) -> float:
	if not color:
		return 0
	color = color.lstrip('#')
	rgb = tuple(int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
	lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
	return lum
