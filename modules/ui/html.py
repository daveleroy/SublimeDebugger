from __future__ import annotations
from ..typecheck import *

from .image import Image
from .style import css, none_css

import re

if TYPE_CHECKING:
	from .layout import Layout

class alignable:
	align_required: int
	align_desired: int
	css: css

	def align(self, width: int):
		...

class element:
	Children = Union[Sequence['element'], 'element', None]

	def __init__(self, is_inline: bool, width: float|None, height: float|None, css: css|None) -> None:
		super().__init__()
		self.layout: Layout|None = None
		self.children: Sequence[element] = []
		self.requires_render = True
		self._max_allowed_width: float|None = None
		self._height = height
		self._width = width
		self.is_inline = is_inline
		self.css = css

	@property
	def css(self):
		return self._css

	@css.setter
	def css(self, css: css|None):
		if css:
			self._css = css
			self.css_id = css.css_id
			self.padding_height = css.padding_height
			self.padding_width = css.padding_width
		else:
			self._css = none_css
			self.css_id = none_css.css_id
			self.padding_height = 0
			self.padding_width = 0

	def height(self, layout: Layout) -> float:
		if self._height is not None:
			return self._height + self.padding_height

		height = 0.0
		height_max = 0.0

		for item in self.children:
			if item is None:
				continue

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

	def dirty(self):
		if self.layout:
			self.layout.dirty()
		self.requires_render = True

	def html_inner(self, layout: Layout) -> str:
		html = ''
		for item in self.children:
			html += item.html(layout)
		return html

	def html(self, layout: Layout) -> str:
		...

	def added(self, layout: Layout) -> None:
		...

	def removed(self) -> None:
		...

	def render(self) -> element.Children:
		...


class span (element):
	Children = Union[Sequence['Children'], 'span', None]

	def __init__(self, width: float|None = None, height: float|None = None, css: css|None = None) -> None:
		super().__init__(True, width, height, css)
		self._items: span.Children = None

	def render(self) -> Children:
		return self._items

	def __getitem__(self, values: Children):
		self._items = values
		return self

	def html(self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		return f'<s id="{self.css_id}">{inner}</s>'


class div (element):
	Children = Union[Sequence['Children'], 'span', 'div', None]

	def __init__(self, width: float|None = None, height: float|None = None, css: css|None = None) -> None:
		super().__init__(False, width, height, css)
		self._items: div.Children = None

	def render(self) -> div.Children:
		return self._items

	def __getitem__(self, values: div.Children):
		self._items = values
		return self

	def html(self, layout: Layout) -> str:
		html = ''
		children_inline = False
		for item in self.children:
			html += item.html(layout)
			children_inline = children_inline or item.is_inline

		h = layout.to_rem(self.height(layout) - self.padding_height)
		w = layout.to_rem(self.width(layout) - self.padding_width)
		if children_inline:
			# this makes it so that divs with an img in them and divs without an img in them all align the same
			return f'<d id="{self.css_id}"><div style="height:{h}rem;width:{w}rem;line-height: {h}rem; padding: {-h+1}rem 0 {h-1}rem 0"><img style="height: {h}rem">{html}</div></d>'
		else:
			return f'<d id="{self.css_id}" style="height:{h}rem;width:{w}rem;">{html}</d>'


def html_escape(text: str) -> str:
	return text.replace(" ", "\u00A0").replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;').replace('\n', '\u00A0')

def html_escape_multi_line(text: str) -> str:
	return text.replace(" ", "\u00A0").replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;').replace('\n', '<br>')

class text (span, alignable):
	def __init__(self, text: str, width: float|None = None, height: float|None = 1, css: css|None = None) -> None:
		super().__init__(width, height, css)
		self.text = text
		self.align_required: int = 0
		self.align_desired: int = len(self.text)

	@property
	def text(self) -> str:
		return self._text

	def align(self, width: int):
		self.text = self.text[0:int(width)]

	@text.setter
	def text(self, text: str):
		self._text = text.replace("\u0000", "\\u0000")

	def width(self, layout: Layout) -> float:
		return len(self.text) + self.padding_width

	def html(self, layout: Layout) -> str:
		self.text_html = html_escape(self._text)
		return f'<s id="{self.css_id}">{self.text_html}</s>'


class click (span):
	def __init__(self, on_click: Callable[[], Any], title: str|None = None) -> None:
		super().__init__()
		self.on_click = on_click
		if title:
			self.title = html_escape(title)
		else:
			self.title = None

	def html(self, layout: Layout) -> str:
		href = layout.register_on_click_handler(self.on_click)
		if self.title:
			return f'<a href={href} title="{self.title}">{self.html_inner(layout)}</a>'
		else:
			return f'<a href={href}>{self.html_inner(layout)}</a>'


class icon (span):
	def __init__(self, image: Image, width: float = 3, height: float = 3, padding: float = 0.5) -> None:
		super().__init__(width=width, height=height)
		self.padding = padding
		self.image = image

	def html(self, layout: Layout) -> str:
		assert self._height
		width = layout.to_rem(self._height - self.padding)
		required_padding = layout.to_rem(self.padding)
		top = layout.to_rem(0.75)
		return f'<s style="position:relative;top:{top}rem;line-height:0rem;padding-right:{required_padding:.2f}rem;"><img style="width:{width:.2f}rem;height:{width:.2f}rem;" src="{self.image.data(layout)}"></s>'

tokenize_re = re.compile(
	r'(0x[0-9A-Fa-f]+)' #matches hex
	r'|([-.0-9]+)' #matches number
	r"|('[^']*')" #matches string '' no escape
	r'|("[^"]*")' #matches string "" no escape
	r'|(.*?)' #other
)


class code(span, alignable):
	def __init__(self, text: str) -> None:
		super().__init__()
		self.text = text.replace("\n", "\\n")
		self.align_required: int = 0
		self.align_desired: int = len(self.text)

	def width(self, layout: Layout) -> float:
		return len(self.text) + self.padding_width

	def align(self, width: int):
		self.text = self.text[0:int(width)]

	def html(self, layout: Layout) -> str:
		self.text_html = ''
		for number, number_hex, string, string_double, other in tokenize_re.findall(self.text):
			string = string_double or string
			number = number or number_hex
			if number:
				self.text_html += f'<s style="color:var(--yellowish);">{number}</s>'
			if string:
				self.text_html += f'<s style="color:var(--greenish);">{html_escape(string)}</s>'
			if other:
				self.text_html += html_escape(other)

		return f'<s style="color:var(--foreground);">{self.text_html}</s>'

def flatten_lists(item_or_list: list[Any]|Any) -> Generator[Any, None, None]:
	if type(item_or_list) == list:
		for item in item_or_list:
			yield from flatten_lists(item)
	else:
		yield item_or_list
		
		