
import sublime
from .layout import Layout, reload_css
from sublime_db.core.typecheck import (
	List,
	Optional,
	Callable,
	Set,
	TYPE_CHECKING
)

# for mypy
if TYPE_CHECKING:
	from .component import Component


_timers = set() #type: Set[Timer]


class Timer:
	def __init__(self, interval: float, callback: Callable[[], None]) -> None:
		self.interval = interval
		self.current_time = 0.0
		self.callback = callback

	def update(self, delta: float) -> None:
		self.current_time += delta
		while self.current_time > self.interval:
			self.callback()
			self.current_time -= self.interval

	def dispose(self) -> None:
		remove_timer(self)


def add_timer(timer: Timer) -> None:
	_timers.add(timer)


def remove_timer(timer: Timer) -> None:
	_timers.discard(timer)


def update(delta: float) -> None:
	for timer in _timers:
		timer.update(delta)


_renderables = [] #type: List[Renderable]
_renderables_remove = [] #type: List[Renderable]
_renderables_add = [] #type: List[Renderable]


def reload() -> None:
	reload_css()
	for renderable in _renderables:
		renderable.force_dirty()


def render() -> None:
	_renderables.extend(_renderables_add)

	renderables_to_update = [] #type: List[Renderable]
	renderables_to_clear = [] #type: List[Renderable]

	for r in _renderables_remove:
		_renderables.remove(r)
		renderables_to_clear.append(r)

	_renderables_add.clear()
	_renderables_remove.clear()

	for r in _renderables:
		if r.render():
			renderables_to_update.append(r)

	if not renderables_to_update and not renderables_to_clear:
		return

	# after we generated the html we need to to update the sublime phantoms
	# if we don't do this on the sublime main thread we will get flickering
	def on_sublime_thread() -> None:
		for r in renderables_to_update:
			r.render_sublime()
		for r in renderables_to_clear:
			r.clear_sublime()

	sublime.set_timeout(on_sublime_thread, 0)


class Renderable:
	def force_dirty(self) -> None:
		assert False

	def render(self) -> bool:
		assert False

	def render_sublime(self) -> None:
		assert False

	def clear_sublime(self) -> None:
		assert False


class Phantom(Layout, Renderable):
	id = 0

	def __init__(self, component: 'Component', view: sublime.View, region: sublime.Region, layout: int = sublime.LAYOUT_INLINE) -> None:
		super().__init__(component)
		self.cachedPhantom = None #type: Optional[sublime.Phantom]
		self.region = region
		self.layout = layout
		self.view = view

		self.set = sublime.PhantomSet(self.view)

		Phantom.id += 1
		self.region_id = 'phantom_{}'.format(Phantom.id)
		self.view.add_regions(self.region_id, [self.region], flags=sublime.DRAW_NO_FILL)
		self._width = 0
		_renderables_add.append(self)

	def force_dirty(self) -> None:
		self.item.dirty()

	def render(self) -> bool:
		width = self.view.viewport_extent()[0]
		if self._width != width:
			self.item.dirty()
			self._width = width

		if super().render() or not self.cachedPhantom:
			html = '''<body id="debug"><style>{}</style>{}</body>'''.format(self.css, self.html)
			# we use the region to track where we should place the new phantom so if text is inserted the phantom will be redrawn in the correct place
			region = self.view.get_regions(self.region_id)[0]
			self.cachedPhantom = sublime.Phantom(region, html, self.layout, self.on_navigate)
			return True
		return False

	def render_sublime(self) -> None:
		assert self.cachedPhantom, "??"
		self.set.update([self.cachedPhantom])

	def clear_sublime(self) -> None:
		self.set.update([])

	def em_width(self) -> float:
		size = self.view.settings().get('font_size') or 12
		return self.view.em_width() / size

	def width(self) -> float:
		size = self.view.settings().get('font_size') or 12
		return self._width / size

	def dispose(self) -> None:
		super().dispose()
		_renderables_remove.append(self)
		self.view.erase_regions(self.region_id)


class Popup(Layout, Renderable):
	def __init__(self, component: 'Component', view: sublime.View, location: int = -1, layout: int = sublime.LAYOUT_INLINE, on_close: Optional[Callable[[], None]] = None) -> None:
		super().__init__(component)
		self.on_close = on_close
		self.location = location
		self.layout = layout
		self.view = view
		self.max_height = 500
		self.max_width = 1000
		self.render()
		view.show_popup(self.html,
                  location=location,
                  max_width=self.max_width,
                  max_height=self.max_height,
                  on_navigate=self.on_navigate,
                  flags=sublime.COOPERATE_WITH_AUTO_COMPLETE,
                  on_hide=self.on_hide)

		_renderables_add.append(self)
		self.is_hidden = False

	def force_dirty(self) -> None:
		self.item.dirty()

	def on_hide(self) -> None:
		self.is_hidden = True
		if self.on_close:
			self.on_close()

	def render(self) -> bool:
		if super().render() or not self.html:
			self.html = '''<body id="debug"><style>{}</style>{}</body>'''.format(self.css, self.html)
			return True
		return False

	def render_sublime(self) -> None:
		self.view.update_popup(self.html)

	def clear_sublime(self) -> None:
		if not self.is_hidden:
			self.view.hide_popup()

	def em_width(self) -> float:
		size = self.view.settings().get('font_size')
		assert size
		return self.view.em_width() / size

	def dispose(self) -> None:
		super().dispose()
		_renderables_remove.append(self)
