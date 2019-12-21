from ..typecheck import *
from ..import core
from . html import div, span, phantom_sizer, Component
from . layout import Layout
from . css import css
from . image import view_background_lightness

import os
import sublime
import threading

class SyntaxHighlightedText:
	def __init__(self, text: str, language: str) -> None:
		self.html = None #type: Optional[str]
		self.text = text
		self.language = language

class LayoutComponent (Layout):
	def __init__(self, item: Union[div, span]) -> None:
		assert item.layout is None, 'item is already added to a layout'
		self.on_click_handlers = {} #type: Dict[int, Callable]
		self.on_click_handlers_id = 0
		self.item = phantom_sizer(div()[item])
		self.add_component(self.item)
		self.requires_render = True
		self.dirty()

	def __getitem__(self, values: 'div.Children'):
		if isinstance(values, Component):
			self.item = phantom_sizer(div()[values])
		else:
			self.item = phantom_sizer(div()[values])

		self.add_component(self.item)
		self.dirty()
		return self

	def dirty(self) -> None:
		from .render import schedule_render
		self.requires_render = True
		schedule_render()

	def remove_component_children(self, item: 'Component') -> None:
		for child in item.children:
			assert child.layout
			child.layout.remove_component(child)

		item.children = []

	def remove_component(self, item: 'Component') -> None:
		self.remove_component_children(item)
		item.removed()
		item.layout = None

	def add_component_children(self, item: 'Component') -> None:
		for item in item.children:
			self.add_component(item)

	def add_component(self, item: 'Component') -> None:
		assert not item.layout, 'This item already has a layout?'
		item.layout = self
		item.added(self)

	def render_component_tree(self, item: 'Component') -> None:
		item.requires_render = False
		self.remove_component_children(item)
		children = item.render()

		if children is None:
			item.children = []
		elif isinstance(children, Component):
			item.children = (children, )
		else:
			item.children = children

		self.add_component_children(item)

		for child in item.children:
			self.render_component_tree(child)

	def render_component(self, item: 'Component') -> None:
		if item.requires_render:
			self.render_component_tree(item)
		else:
			for child in item.children:
				self.render_component(child)

	def render(self) -> bool:
		if not self.requires_render:
			return False

		self.on_click_handlers = {}
		self.requires_render = False

		if self.item:
			self.render_component(self.item)
			self.run_syntax_highlight()
			self.html = '''<body id="debug"><style>{}</style>{}</body>'''.format(css.all, self.item.html(self))
		else:
			self.html = ""

		return True

	def syntax_highlight(self, text: str, language: str) -> str:
		return self.text

	def dispose(self) -> None:
		self.remove_component(self.item)

	def on_navigate(self, path: str) -> None:
		id = int(path)
		if id in self.on_click_handlers:
			self.on_click_handlers[id]()

	def register_on_click_handler(self, callback: 'Callable') -> str:
		self.on_click_handlers_id += 1
		id = self.on_click_handlers_id
		self.on_click_handlers[id] = callback
		return str(id)

class LayoutView (LayoutComponent):
	def __init__(self, item: 'Component', view: sublime.View) -> None:
		super().__init__(item)
		self.view = view
		self._width = 0.0
		self._height = 0.0
		self._lightness = 0.0
		self._em_width = 1.0
		self.update()
		self._highlighter = None
		self._unhighlightedSyntaxHighlightedTexts = []
		self._syntaxHighlightCache = {} #type: dict
		try:
			from mdpopups import SublimeHighlight
			scheme = view.settings().get('color_scheme')
			self._highlighter = SublimeHighlight(scheme)
		except ImportError as e:
			core.log_info('syntax highlighting disabled no mdpopups')

	def em_width(self) -> float:
		return self._em_width

	def width(self) -> float:
		return self._width

	def height(self) -> float:
		return self._height

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

		for item in self._unhighlightedSyntaxHighlightedTexts:
			cache = self._syntaxHighlightCache.setdefault(item.language, {})
			if item.text in cache:
				item.html = cache[item.text]
			else:
				try:
					item.html = self._highlighter.syntax_highlight(item.text, item.language, inline=True)
					cache[item.text] = item.html
				except:
					core.log_exception()

		self._unhighlightedSyntaxHighlightedTexts = []

	def update(self) -> None:
		font_size = self.view.settings().get('font_size') or 12
		lightness = view_background_lightness(self.view)
		size = self.view.viewport_extent()
		em_width = self.view.em_width()
		width = size[0] / em_width
		height = size[1] / em_width
		em_width = (self.view.em_width() or 12) / font_size

		if em_width != self._em_width or self._width != width or self._height != height or self._lightness != lightness:
			self._em_width = em_width
			self._width = width
			self._height = height
			self._lightness = lightness
			self.item.dirty()

	def force_dirty(self) -> None:
		self.item.dirty()
