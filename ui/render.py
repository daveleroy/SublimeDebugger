
from .image import view_background_lightness
from .layout import Layout, reload_css
from sublime_db import core

import sublime
import threading

from sublime_db.core.typecheck import (
	List,
	Optional,
	Callable,
	Set,
	Dict,
	TYPE_CHECKING
)
# for mypy
if TYPE_CHECKING:
	from .component import Component


class Timer:
	def __init__(self, callback: Callable[[], None], interval: float, repeat: bool) -> None:
		self.interval = interval
		self.callback = callback
		self.cancelable = core.main_loop.call_later(interval, self.on_complete)
		self.repeat = repeat

	def schedule(self) -> None:
		self.cancelable = core.main_loop.call_later(self.interval, self.on_complete)

	def on_complete(self) -> None:
		self.callback()
		if self.repeat:
			self.schedule()

	def dispose(self) -> None:
		self.cancelable.cancel()


_renderables = [] #type: List[Renderable]
_renderables_remove = [] #type: List[Renderable]
_renderables_add = [] #type: List[Renderable]


def reload() -> None:
	update()
	reload_css()
	for renderable in _renderables:
		renderable.force_dirty()
	schedule_render()


_render_scheduled = False


def schedule_render() -> None:
	global _render_scheduled
	if _render_scheduled:
		return

	_render_scheduled = True
	core.run(render_scheduled())


@core.async
def render_scheduled() -> None:
	global _render_scheduled
	render()
	_render_scheduled = False


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


def update() -> None:
	for item in _renderables:
		item.update()


class Renderable:
	def force_dirty(self) -> None:
		assert False

	def update(self) -> None:
		assert False

	def render(self) -> bool:
		assert False

	def render_sublime(self) -> None:
		assert False

	def clear_sublime(self) -> None:
		assert False


class SyntaxHighlightedText:
	def __init__(self, text: str, language: str) -> None:
		self.html = None #type: Optional[str]
		self.text = text
		self.language = language


class LayoutView (Layout):
	def __init__(self, item: 'Component', view: sublime.View) -> None:
		super().__init__(item)
		self.view = view
		self._width = 0
		self._lightness = 0.0
		self._em_width = 1.0
		self.update()
		self._highlighter = None
		self._unhighlightedSyntaxHighlightedTexts = []
		self._syntaxHighlightCache = {} #type: Dict[]
		try:
			import mdpopups
			scheme = view.settings().get('color_scheme')
			self._highlighter = mdpopups.SublimeHighlight(scheme)
		except ImportError as e:
			core.log('syntax highlighting disabled no mdpopups')

	def em_width(self) -> float:
		return self._em_width

	def width(self) -> float:
		return self._width

	def luminocity(self) -> float:
		return self._lightness

	def syntax_highlight(self, text: str, language: str) -> SyntaxHighlightedText:
		item = SyntaxHighlightedText(text, language)
		self._unhighlightedSyntaxHighlightedTexts.append(item)
		return item

	# we run syntax highlighting in the main thread all at once before html is generated
	# This speeds it up a ton since its interacting with sublime's views which seems
	# we cache all the results because it is really really slow still...
	def run_syntax_highlight(self) -> None:
		if not self._highlighter:
			return
		event = threading.Event()

		def run():
			for item in self._unhighlightedSyntaxHighlightedTexts:
				cache = self._syntaxHighlightCache.setdefault(item.language, {})
				if item.text in cache:
					item.html = cache[item.text]
				else:
					item.html = self._highlighter.syntax_highlight(item.text, item.language)
					cache[item.text] = item.html
			self._unhighlightedSyntaxHighlightedTexts = []
			event.set()

		sublime.set_timeout(run)
		event.wait()

	def update(self) -> None:
		font_size = self.view.settings().get('font_size') or 12
		lightness = view_background_lightness(self.view)
		width = self.view.viewport_extent()[0] / font_size
		em_width = (self.view.em_width() or 12) / font_size

		if em_width != self._em_width or self._width != width or self._lightness != lightness:
			self._em_width = em_width
			self._width = width
			self._lightness = lightness
			self.item.dirty()

	def force_dirty(self) -> None:
		self.item.dirty()


class Phantom(LayoutView, Renderable):
	id = 0

	def __init__(self, component: 'Component', view: sublime.View, region: sublime.Region, layout: int = sublime.LAYOUT_INLINE) -> None:
		super().__init__(component, view)
		self.cachedPhantom = None #type: Optional[sublime.Phantom]
		self.region = region
		self.layout = layout
		self.view = view

		self.set = sublime.PhantomSet(self.view)

		Phantom.id += 1
		self.region_id = 'phantom_{}'.format(Phantom.id)
		self.view.add_regions(self.region_id, [self.region], flags=sublime.DRAW_NO_FILL)
		self.update()
		_renderables_add.append(self)

	def render(self) -> bool:
		if super().render() or not self.cachedPhantom:
			html = '''<body id="debug"><style>{}</style>{}</body>'''.format(self.css, self.html)
			# we use the region to track where we should place the new phantom so if text is inserted the phantom will be redrawn in the correct place
			regions = self.view.get_regions(self.region_id)
			if regions:
				self.cachedPhantom = sublime.Phantom(regions[0], html, self.layout, self.on_navigate)
			return True
		return False

	def render_sublime(self) -> None:
		assert self.cachedPhantom, "??"
		self.set.update([self.cachedPhantom])

	def clear_sublime(self) -> None:
		self.set.update([])

	def dispose(self) -> None:
		super().dispose()
		_renderables_remove.append(self)
		self.view.erase_regions(self.region_id)
		schedule_render()


class Popup(LayoutView, Renderable):
	def __init__(self, component: 'Component', view: sublime.View, location: int = -1, layout: int = sublime.LAYOUT_INLINE, on_close: Optional[Callable[[], None]] = None) -> None:
		super().__init__(component, view)
		self.on_close = on_close
		self.location = location
		self.layout = layout
		self.max_height = 500
		self.max_width = 1000
		self.render()
		view.show_popup(self.html,
                  location=location,
                  max_width=self.max_width,
                  max_height=self.max_height,
                  on_navigate=self.on_navigate,
                  flags=sublime.COOPERATE_WITH_AUTO_COMPLETE | sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                  on_hide=self.on_hide)

		_renderables_add.append(self)
		self.is_hidden = False

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

	def dispose(self) -> None:
		super().dispose()
		_renderables_remove.append(self)
