from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

from .. import core
from .layout import Layout

import sublime

class Phantom(Layout):
	def __init__(self, view: sublime.View, region: sublime.Region|int, layout: int = sublime.LAYOUT_INLINE, name: str|None = None) -> None:
		super().__init__(view)
		self.region = sublime.Region(region) if isinstance(region, int) else region
		self.layout = layout
		self.view = view
		self.pid: int|None = None
		self.stats.name = name or self.stats.name
		self.update()

	def render(self) -> bool:
		timer = core.stopwatch()
		updated = super().render()

		# don't need to update phantom
		if not updated and self.pid is not None:
			return False

		self.render_phantom()

		self.stats.render_time = timer.elapsed()
		self.stats.render_time_total += self.stats.render_time
		self.stats.render_count += 1
		return True

	def render_region(self):
		region = self.region
		if region.a == -1:
			return sublime.Region(self.view.size())
		return region

	def render_phantom(self):
		region = self.render_region()
		if self.pid: self.view.erase_phantom_by_id(self.pid)
		self.pid = self.view.add_phantom('debugger', region, self.html, self.layout, self.on_navigate)

	def render_if_out_of_position(self):
		# if this phantom must be rendered just render it
		# otherwise we can just render the phantom without generating new html and stuff if its out of position
		if self.requires_render:
			self.render()
			return

		region = self.render_region()
		at: list[sublime.Region] = self.view.query_phantoms([self.pid]) #type: ignore (the typing is wrong its a list of regions)
		if at and at[0] == region:
			return

		core.info('rendering phantom it is out of position or deleted')
		self.render_phantom()

	def dispose(self) -> None:
		super().dispose()
		if self.pid: self.view.erase_phantom_by_id(self.pid)


@dataclass
class Html:
	html: str
	on_navigate: Callable[[str], Any]|None = None

def region_from_region_or_position(region: sublime.Region|int):
	return region if isinstance(region, sublime.Region) else sublime.Region(region)

class RawPhantom:
	def __init__(self, view: sublime.View, region: sublime.Region|int, html: str, layout: int = sublime.LAYOUT_INLINE, on_navigate: Callable[[str], Any]|None = None) -> None:
		self.view = view
		self.pid = self.view.add_phantom(f'debugger', region_from_region_or_position(region), html, layout, on_navigate)

	def dispose(self) -> None:
		self.view.erase_phantom_by_id(self.pid)


class RawAnnotation:
	def __init__(self, view: sublime.View, region: sublime.Region|int, html: str):
		self.view = view
		self.id = str(id(self))
		view.add_regions(self.id, [region_from_region_or_position(region)], annotation_color="#fff0", annotations=[html])

	def dispose(self):
		self.view.erase_regions(self.id)


class Popup(Layout):
	def __init__(self, view: sublime.View, location: int = -1, on_close: Callable[[], None]|None = None) -> None:
		super().__init__(view)

		self.on_close = on_close
		self.location = location
		self.max_height = 500
		self.max_width = 1000
		self.is_closed = False
		self.created_popup = False

	def on_hide(self) -> None:
		self.is_closed = True
		self.dispose()

		if self.on_close:
			self.on_close()

	def render(self) -> bool:
		if self.is_closed:
			return False

		timer = core.stopwatch()
		updated = super().render()
		if not updated:
			return False

		self.create_or_update_popup()

		self.stats.render_time = timer.elapsed()
		self.stats.render_time_total += self.stats.render_time
		self.stats.render_count += 1
		return True

	def create_or_update_popup(self):
		if self.is_closed:
			return False

		if self.created_popup:
			self.view.update_popup(self.html)
		else:
			self.created_popup = True
			self.view.show_popup(
				self.html,
				location=self.location,
				max_width=self.max_width,
				max_height=self.max_height,
				on_navigate=self.on_navigate,
				flags=sublime.COOPERATE_WITH_AUTO_COMPLETE | sublime.HIDE_ON_MOUSE_MOVE_AWAY,
				on_hide=self.on_hide
			)

	def dispose(self) -> None:
		super().dispose()
		if not self.is_closed:
			self.is_closed = True
			self.view.hide_popup()
