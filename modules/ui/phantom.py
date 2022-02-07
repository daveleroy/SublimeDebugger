from __future__ import annotations
from ..typecheck import *

from .. import core
from .html import span, div
from .layout import Layout
from .debug import DEBUG_TIMING

import sublime

render_count = 0

class Phantom(Layout):
	id = 0
	
	def __init__(self, view: sublime.View, region: sublime.Region, layout: int = sublime.LAYOUT_INLINE) -> None:
		super().__init__(div(), view)
		self.cached_phantom: sublime.Phantom|None = None
		self.region = region
		self.layout = layout
		self.view = view

		self.set = sublime.PhantomSet(self.view)

		Phantom.id += 1

		# we use the region to track where we should place the new phantom so if text is inserted the phantom will be redrawn in the correct place
		self.region_id = 'phantom_{}'.format(Phantom.id)
		self.view.add_regions(self.region_id, [self.region], flags=sublime.DRAW_NO_FILL)
		self.update()

	def render(self) -> bool:
		total = core.stopwatch()
		updated = super().render()
		
		# don't need to update phantom
		if not updated and self.cached_phantom:
			return False

		# no phantom to update...
		regions = self.view.get_regions(self.region_id)
		if not regions:
			return False

		global render_count
		render_count += 1
		
		timer = core.stopwatch('phantom')
		self.cached_phantom = sublime.Phantom(regions[0], self.html, self.layout, self.on_navigate)
		self.set.update([self.cached_phantom])
		if DEBUG_TIMING: timer()
		self.last_render_time = total.elapsed()
		return True

	def dispose(self) -> None:
		super().dispose()
		self.view.erase_regions(self.region_id)
		self.set.update([])


class Popup(Layout):
	def __init__(self, view: sublime.View, location: int = -1, on_close: Optional[Callable[[], None]] = None) -> None:
		super().__init__(div(), view)

		self.on_close = on_close
		self.location = location
		self.max_height = 500
		self.max_width = 1000
		self.render()

		self.is_hidden = False

	def on_hide(self) -> None:
		self.is_hidden = True
		if self.on_close:
			self.on_close()

	def render(self) -> bool:
		total = core.stopwatch()
		updated = super().render()
		if not updated:
			return False

		timer = core.stopwatch('popup')
	
		if not self.view.is_popup_visible():
			self.view.show_popup(
				self.html,
				location=self.location,
				max_width=self.max_width,
				max_height=self.max_height,
				on_navigate=self.on_navigate,
				flags=sublime.COOPERATE_WITH_AUTO_COMPLETE | sublime.HIDE_ON_MOUSE_MOVE_AWAY,
				on_hide=self.on_hide
			)
		else:
			self.view.update_popup(self.html)
		
		if DEBUG_TIMING: timer()
		self.last_render_time = total.elapsed()
		return True

	def dispose(self) -> None:
		super().dispose()
		if not self.is_hidden:
			self.is_hidden = True
			self.view.hide_popup()
