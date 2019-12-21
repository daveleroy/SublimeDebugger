from ..typecheck import *
from . component import Component
from . layout import Layout
from . image import Image
from . css import css, div_inline_css, icon_css


class element(Component):
	def __init__(self, is_inline: bool, width: Optional[float], height: Optional[float], css: Optional[css]) -> None:
		super().__init__()
		self._height = height
		self._width = width
		self.is_inline = is_inline
		if css:
			self.className = css.class_name
			self.padding_height = css.padding_height
			self.padding_width = css.padding_width
		else:
			self.padding_height = 0
			self.padding_width = 0

	def height(self, layout: Layout) -> float:
		if self._height is not None:
			return self._height + self.padding_height

		height = 0.0
		height_max = 0.0

		for item in self.children:
			height += item.height(layout)
			if item.is_inline and height > height_max:
				height_max = max(height_max, height)
				height = 0.0

		return max(height_max, height) + self.padding_height

	def width(self, layout: Layout) -> float:
		if self._width is not None:
			return self._width + self.padding_width

		width = 0.0
		width_max = 0.0

		for item in self.children:
			width += item.width(layout)
			if not item.is_inline and width > width_max:
				width_max = max(width_max, width)
				width = 0.0

		return max(width_max, width) + self.padding_width

class span (element):
	Children = Optional[Union[Sequence['span'], 'span']]

	def __init__(self, width: Optional[float] = None, height: Optional[float] = None, css: Optional[css] = None) -> None:
		super().__init__(True, width, height, css)
		self._items = None #type: span.Children

	def render(self) -> 'span.Children':
		return self._items

	def __getitem__(self, values: 'span.Children'):
		self._items = values
		return self

	def html(self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		h = self.height(layout)
		w = self.width(layout)
		html = '<span class="{}" style="line-height:{}rem;">{}</span>'.format(self.className, h, inner)
		return html

class div (element):
	Children = Optional[Union[Sequence['div'], Sequence['span'], 'div', 'span']]

	def __init__(self, width: Optional[float] = None, height: Optional[float] = None, css: Optional[css] = None) -> None:
		super().__init__(False, width, height, css)
		self._items = None #type: div.Children

	def render(self) -> 'div.Children':
		return self._items

	def __getitem__(self, values: 'div.Children'):
		self._items = values
		return self

	def html(self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		h = self.height(layout) - self.padding_height
		w = self.width(layout) - self.padding_width

		if self.children and self.children[0].is_inline:
			html = '<div class= "{} {}" style="height:{}rem;width:{}rem;line-height:{}rem"><img style="height:2.5rem;">{}</div>'.format(div_inline_css.class_name, self.className, h, w, h, inner)
		else:
			html = '<div class="{}" style="height:{}rem;width:{}rem;">{}</div>'.format(self.className, h, w, inner)
		return html


# uses an img tag to force the width of the phantom to be the width of the item being rendered
class phantom_sizer (div):
	def __init__(self, item: Union[div, span]) -> None:
		super().__init__()
		self.item = item

	def render(self) -> div.Children:
		return self.item

	def html(self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		h = self.height(layout)
		w = self.width(layout)
		html = '<div class="{}" style="height:{}rem;"><img style="width:{}rem;">{}</div>'.format(self.className, h, w, inner)
		return html


html_escape_table = {
	"&": "&amp;",
	">": "&gt;",
	"<": "&lt;",
	" ": "\u00A0" # HACK spaces inside <a> tags are not clickable. We replaces spaces with no break spaces
}

def html_escape(text: str) -> str:
	return "".join(html_escape_table.get(c, c) for c in text)

class text (span):
	def __init__(self, text: str, width: Optional[float] = None, height: Optional[float] = None, css: Optional[css] = None) -> None:
		super().__init__(width, height, css)
		self.text = text.replace("\u0000", "\\u0000")
		self.text_html = html_escape(self.text)

	def width(self, layout: Layout) -> float:
		return len(self.text) + self.padding_width

	def html(self, layout: Layout) -> str:
		h = self.height(layout)
		html = '<span class="{}" style="line-height:{}rem;">{}</span>'.format(self.className, h, self.text_html)
		return html


class click (span):
	def __init__(self, on_click: Callable[[], None]) -> None:
		super().__init__()
		self.on_click = on_click

	def html(self, layout: Layout) -> str:
		href = layout.register_on_click_handler(self.on_click)
		html = '<a href={}>{}</a>'.format(href, self.html_inner(layout))
		return html

class icon (span):
	def __init__(self, image: Image) -> None:
		super().__init__(width=2.5, height=2.5, css=icon_css)
		self.image = image

	def html(self, layout: Layout) -> str:
		return '''<span class="{}"><img style="width:2.5rem;height:2.5rem;" src="{}"></span>'''.format(self.className, self.image.data(layout))

class code(span):
	def __init__(self, text: str, language: str = 'c++') -> None:
		super().__init__()
		self.text = text.replace("\n", "")
		self.text_html = html_escape(self.text)
		self.language = language

	def added(self, layout: Layout) -> str:
		self.highlight = layout.syntax_highlight(self.text, self.language)

	def width(self, layout: Layout) -> float:
		return len(self.text) + self.padding_width

	def html(self, layout: Layout) -> str:
		h = self.height(layout)
		text_html = self.highlight.html or self.text_html
		html = '<span class="{}" style="line-height:{}rem;">{}</span>'.format(self.className, h, text_html)
		return html
