from __future__ import annotations
from ..typecheck import *

from .. import core
from .layout import Layout
from .debug import DEBUG_TIMING

import sublime

render_count = 0

class Phantom(Layout):
	id = 0
	
	def __init__(self, view: sublime.View, region: sublime.Region, layout: int = sublime.LAYOUT_INLINE) -> None:
		super().__init__(view)
		self.cached_phantom: sublime.Phantom|None = None
		self.region = region
		self.layout = layout
		self.view = view

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
		self.view.erase_phantoms(self.region_id)
		self.view.add_phantom(self.region_id, regions[0], self.html, self.layout, self.on_navigate)
		if DEBUG_TIMING: timer()
		self.last_render_time = total.elapsed()
		return True

	def dispose(self) -> None:
		super().dispose()
		self.view.erase_regions(self.region_id)
		self.view.erase_phantoms(self.region_id)


class RawPhantom:	
	def __init__(self, view: sublime.View, region: sublime.Region, html: str, layout: int = sublime.LAYOUT_INLINE, on_navigate: Callable[[str], Any]|None = None) -> None:
		self.region = region
		self.view = view
		self.pid = self.view.add_phantom(f'{id(self)}', region, html, layout, on_navigate)

	def dispose(self) -> None:
		self.view.erase_phantom_by_id(self.pid)


class Popup(Layout):
	def __init__(self, view: sublime.View, location: int = -1, on_close: Optional[Callable[[], None]] = None) -> None:
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
		
		total = core.stopwatch()
		updated = super().render()
		if not updated:
			return False

		timer = core.stopwatch('popup')

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
			
		if DEBUG_TIMING: timer()
		self.last_render_time = total.elapsed()
		return True

	def dispose(self) -> None:
		super().dispose()
		if not self.is_closed:
			self.is_closed = True
			self.view.hide_popup()
