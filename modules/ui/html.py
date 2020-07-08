from ..typecheck import *
from . layout import Layout
from . image import Image
from . css import css, div_inline_css, icon_css, none_css


class element:
	def __init__(self, is_inline: bool, width: Optional[float], height: Optional[float], css: Optional[css]) -> None:
		super().__init__()
		self.layout = None #type: Optional[Layout]
		self.children = [] #type: Sequence[element]
		self.requires_render = True
		self._max_allowed_width = None
		self._height = height
		self._width = width
		self.is_inline = is_inline
		if css:
			self.css = css
			self.className = css.class_name
			self.padding_height = css.padding_height
			self.padding_width = css.padding_width
		else:
			self.css = none_css
			self.className = none_css.class_name
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

		if self._max_allowed_width:
			return self._max_allowed_width

		width = 0.0
		width_max = 0.0

		for item in self.children:
			width += item.width(layout)
			if not item.is_inline and width > width_max:
				width_max = max(width_max, width)
				width = 0.0

		return max(width_max, width) + self.padding_width

	def add_class(self, name: str) -> None:
		self.className += ' '
		self.className += name

	def dirty(self):
		if self.layout:
			self.layout.dirty()
		self.requires_render = True

	def html_inner(self, layout: Layout) -> str:
		html = []
		for child in self.children:
			html.append(child.html(layout))
		return ''.join(html)

	def html(self, layout: Layout) -> str:
		...

	def added(self, layout: Layout) -> None:
		...

	def removed(self) -> None:
		...

	def render(self) -> Optional[Union[Sequence['element'], 'element']]:
		...


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
		h = self.height(layout) * layout.rem_width_scale()
		w = self.width(layout) * layout.rem_width_scale()
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
		h = (self.height(layout) - self.padding_height) * layout.rem_width_scale()
		w = (self.width(layout) - self.padding_width) * layout.rem_width_scale()

		if self.children and self.children[0].is_inline:
			html = '<div class= "{} {}" style="height:{}rem;width:{}rem;line-height:{}rem"><img style="height:1.6rem;">{}</div>'.format(div_inline_css.class_name, self.className, h, w, h, inner)
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
		h = self.height(layout) * layout.rem_width_scale()
		w = self.width(layout) * layout.rem_width_scale()
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
	def __init__(self, text: str, width: Optional[float] = None, height: Optional[float] = 1, css: Optional[css] = None) -> None:
		super().__init__(width, height, css)
		self.text = text.replace("\u0000", "\\u0000")

	@property
	def text(self) -> str:
		return self._text

	@text.setter
	def text(self, text: str):
		self._text = text.replace("\u0000", "\\u0000")
		self.text_html = html_escape(self._text)

	def width(self, layout: Layout) -> float:
		return len(self.text) + self.padding_width

	def html(self, layout: Layout) -> str:
		h = self.height(layout) * layout.rem_width_scale()
		html = '<span class="{}">{}</span>'.format(self.className, self.text_html)
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
		super().__init__(width=3, height=1, css=icon_css)
		self.image = image

	def html(self, layout: Layout) -> str:
		actual_rem_width = 1.6 / layout.rem_width_scale()
		required_padding = 3 - actual_rem_width
		return f'''<span style="padding-right:{required_padding:.2f}rem;" class="{self.className}"><img style="width:1.6rem;height:1.6rem;" src="{self.image.data(layout)}"></span>'''

import re
tokenize_re = re.compile(
	r'(0x[0-9A-Fa-f]+)' #matches hex
	r'|([-.0-9]+)' #matches number
	r"|('[^']*')" #matches string '' no escape
	r'|("[^"]*")' #matches string "" no escape
	r'|(.*?)' #other
)

class code(span):
	def __init__(self, text: str, language: str = 'c++') -> None:
		super().__init__()
		self.text = text.replace("\n", "")
		self.text_html = ''
		for number, number_hex, string, string_double, other in tokenize_re.findall(self.text):
			string = string_double or string
			number = number or number_hex
			if number:
				self.text_html += '<span style="color:var(--yellowish);">{}</span>'.format(number)
			if string:
				self.text_html += '<span style="color:var(--greenish);">{}</span>'.format(html_escape(string))
			if other:
				self.text_html += '<span style="color:var(--foreground);">{}</span>'.format(html_escape(other))

		self.language = language


	def width(self, layout: Layout) -> float:
		return len(self.text) + self.padding_width

	def html(self, layout: Layout) -> str:
		h = self.height(layout) * layout.rem_width_scale()
		html = '<span class="{}" style="line-height:{}rem;">{}</span>'.format(self.className, h, self.text_html)
		return html
