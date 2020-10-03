from __future__ import annotations
from ..typecheck import *
from .. import core
from . html import span, div, element, phantom_sizer
from . layout_view import LayoutView

import sublime
import threading


class Timer:
	def __init__(self, callback: Callable[[], None], interval: float, repeat: bool) -> None:
		self.interval = interval
		self.callback = callback
		self.cancelable = core.call_later(interval, self.on_complete)
		self.repeat = repeat

	def schedule(self) -> None:
		self.cancelable = core.call_later(self.interval, self.on_complete)

	def on_complete(self) -> None:
		self.callback()
		if self.repeat:
			self.schedule()

	def dispose(self) -> None:
		self.cancelable.cancel()


_renderables: List[Renderable] = []
_renderables_remove: List[Renderable] = []
_renderables_add: List[Renderable] = []


def reload() -> None:
	update()
	for renderable in _renderables:
		renderable.force_dirty()
	schedule_render()


_render_scheduled = False


def schedule_render() -> None:
	global _render_scheduled
	if _render_scheduled:
		return

	_render_scheduled = True
	core.call_soon(render_scheduled)


def render_scheduled() -> None:
	global _render_scheduled
	perform_render()
	_render_scheduled = False


def perform_render() -> None:
	_renderables.extend(_renderables_add)
	_renderables_add.clear()

	for r in _renderables_remove:
		_renderables.remove(r)

	_renderables_remove.clear()

	if False:
		import cProfile
		with cProfile.Profile() as pr:
			for r in _renderables:
				r.render()

		pr.print_stats(sort='cumtime')
	else:
		for r in _renderables:
			r.render()


def update() -> None:
	for item in _renderables:
		item.update()


class Renderable(Protocol):
	def force_dirty(self) -> None:
		assert False

	def update(self) -> None:
		assert False

	def render(self) -> bool:
		assert False


class Phantom(LayoutView, Renderable):
	id = 0

	def __init__(self, component: Union[span, div], view: sublime.View, region: sublime.Region, layout: int = sublime.LAYOUT_INLINE) -> None:
		super().__init__(component, view)
		self.cachedPhantom = None #type: Optional[sublime.Phantom]
		self.region = region
		self.layout = layout
		self.view = view

		self.set = sublime.PhantomSet(self.view)

		Phantom.id += 1

		# we use the region to track where we should place the new phantom so if text is inserted the phantom will be redrawn in the correct place
		self.region_id = 'phantom_{}'.format(Phantom.id)
		self.view.add_regions(self.region_id, [self.region], flags=sublime.DRAW_NO_FILL)
		self.update()
		_renderables_add.append(self)

	def render(self) -> bool:
		regions = self.view.get_regions(self.region_id)
		if regions and (super().render() or not self.cachedPhantom):
			self.cachedPhantom = sublime.Phantom(regions[0], self.html, self.layout, self.on_navigate)
			self.set.update([self.cachedPhantom])
			return True
		return False

	def dispose(self) -> None:
		super().dispose()
		self.view.erase_regions(self.region_id)
		_renderables_remove.append(self)
		self.set.update([])


class Popup(LayoutView, Renderable):
	def __init__(self, component: Union[span, div], view: sublime.View, location: int = -1, on_close: Optional[Callable[[], None]] = None) -> None:
		super().__init__(component, view)
		self.on_close = on_close
		self.location = location
		self.max_height = 500
		self.max_width = 1000
		self.render()

		view.show_popup(
			self.html,
			location=location,
			max_width=self.max_width,
			max_height=self.max_height,
			on_navigate=self.on_navigate,
			flags=sublime.COOPERATE_WITH_AUTO_COMPLETE | sublime.HIDE_ON_MOUSE_MOVE_AWAY,
			on_hide=self.on_hide
		)

		_renderables_add.append(self)
		self.is_hidden = False

	def on_hide(self) -> None:
		self.is_hidden = True
		if self.on_close:
			self.on_close()

	def render(self) -> bool:
		if super().render() or not self.html:
			self.view.update_popup(self.html)
			return True
		return False

	def dispose(self) -> None:
		super().dispose()
		_renderables_remove.append(self)
		if not self.is_hidden:
			self.view.hide_popup()
