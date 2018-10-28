
from debug.core.typecheck import (
	List,
	Optional,
	Callable,
	Set,
	TYPE_CHECKING
)

#for mypy
if TYPE_CHECKING: from .component import Component

from .layout import Layout

import sublime

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

	def dispose (self) -> None:
		remove_timer(self)

def add_timer (timer: Timer) -> None:
	_timers.add(timer)

def remove_timer (timer: Timer) -> None:
	_timers.discard(timer)

def update (delta: float) -> None:
	for timer in _timers:
		timer.update(delta)

_renderables = [] #type: List[Renderable]
_renderables_remove = [] #type: List[Renderable]
_renderables_add = [] #type: List[Renderable]

def render () -> None:
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
	def render(self) -> bool:
		assert False
	def render_sublime(self) -> None:
		assert False
	def clear_sublime(self) -> None:
		assert False

class Phantom(Layout, Renderable):
	def __init__(self, component: 'Component', view: sublime.View, region: sublime.Region, layout: int = sublime.LAYOUT_INLINE) -> None:
		super().__init__(component)
		self.cachedPhantom = None #type: Optional[sublime.Phantom]
		self.region = region
		self.layout = layout
		self.view = view
		self.set = sublime.PhantomSet(self.view)
		_renderables_add.append(self)
	def render(self) -> bool:
		if super().render() or not self.cachedPhantom:
			html = '''<body id="debug"><style>{}</style>{}</body>'''.format(self.css, self.html)
			self.cachedPhantom = sublime.Phantom(self.region, html, self.layout, self.on_navigate)
			return True
		return False

	def render_sublime(self) -> None:
		assert self.cachedPhantom, "??"
		self.set.update([self.cachedPhantom])

	def clear_sublime(self) -> None:
		self.set.update([])

	def em_width(self) -> float:
		size = self.view.settings().get('font_size')
		assert size
		return self.view.em_width() / size

	def dispose(self) -> None:
		super().dispose()
		_renderables_remove.append(self)


class Popup(Layout, Renderable):
	def __init__(self, component: 'Component', view: sublime.View, location: int = -1, layout: int = sublime.LAYOUT_INLINE, on_close: Optional[Callable[[], None]] = None) -> None:
		super().__init__(component)
		self.on_close = on_close
		self.location = location
		self.layout = layout
		self.view = view
		self.max_height = 500
		self.max_width = 500
		self.render()
		view.show_popup(self.html, 
			location = location,
			max_width = self.max_width, 
			max_height = self.max_height, 
			on_navigate = self.on_navigate,
			flags = sublime.HIDE_ON_MOUSE_MOVE_AWAY,
			on_hide = self.on_hide)

		_renderables_add.append(self)

	def on_hide(self) -> None:
		if self.on_close:
			self.on_close()
		self.dispose()

	def render(self) -> bool:
		if super().render() or not self.html:
			self.html = '''<body id="debug"><style>{}</style>{}</body>'''.format(self.css, self.html)
			return True
		return False

	def render_sublime(self) -> None:
		self.view.update_popup(self.html)

	def em_width(self) -> float:
		size = self.view.settings().get('font_size')
		assert size
		return self.view.em_width() / size

	def dispose(self) -> None:
		super().dispose()
		_renderables_remove.append(self)


