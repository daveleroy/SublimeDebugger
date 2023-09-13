from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Iterable, Sequence, TypedDict, Union
from ..core.typing_extensions import Unpack

from .image import Image
from .css import css

import re

if TYPE_CHECKING:
	from .layout import Layout

class alignable:
	align_required: int
	align_desired: int
	css: css

	def align(self, width: float) -> float: ...

HtmlResponse = Union[str, Iterable['HtmlResponse']]


class element:
	Children = Union[Sequence['element'], 'element', None]

	def __init__(self, is_inline: bool, width: float|None, height: float|None, css: css|None) -> None:
		super().__init__()
		self.layout: Layout = None #type: ignore
		self.children: list[element] = []
		self.requires_render = True
		self._available_block_width: float|None = None
		self.height = height
		self.width = width
		self.is_inline = is_inline

		if css:
			self.css_id = css.id
			self.css_padding_height = css.padding_height
			self.css_padding_width = css.padding_width
		else:
			self.css_id = None
			self.css_padding_height = 0
			self.css_padding_width = 0


	def html_height(self) -> float: ...

	def dirty(self):
		if self.layout:
			self.layout.dirty()
		self.requires_render = True

	def _html_inner_child(self, child: element):
		return child.html()

	def html_inner(self) -> HtmlResponse:
		return map(self._html_inner_child, self.children)

	def html(self) -> HtmlResponse:
		...

	def added(self) -> None: ...
	def removed(self) -> None: ...
	def render(self) -> element.Children: ...


class SpanParams(TypedDict, total=False):
	on_click: Callable[[], Any]|None
	title: str|None


class span (element):
	Children = Union[Sequence['Children'], 'span', None]

	def __init__(self, css: css|None = None, **kwargs: Unpack[SpanParams]) -> None:
		super().__init__(True, None, None, css)
		self.kwargs = kwargs
		self._items: span.Children = None

	def render(self) -> Children: #type: ignore
		return self._items

	def __getitem__(self, values: Children):
		self._items = values
		return self

	# height of a span is always just fixed it doesn't really since it does not change the layout
	def html_height(self) -> float:
		if self.height is not None:
			return self.height + self.css_padding_height

		return self.css_padding_height

	def html_tag_and_attrbutes(self):
		attributes = f'id="{self.css_id}"' if self.css_id else ''
		tag = 's'

		if on_click := self.kwargs.get('on_click'):
			tag = 'a'
			id = self.layout.register_on_click_handler(on_click)
			attributes += f' href="{id}"'

		if title := self.kwargs.get('title'):
			attributes += f' title="{title}"'

		return (tag, attributes)

	def html(self) -> HtmlResponse:
		inner = self.html_inner()
		tag, attributes = self.html_tag_and_attrbutes()
		return [
			f'<{tag} {attributes}>',
				inner,
			f'</{tag}>',
		]


class div (element):
	Children = Union[Sequence['Children'], 'span', 'div', None]

	def __init__(self, width: float|None = None, height: float|None = None, css: css|None = None) -> None:
		super().__init__(False, width, height, css)
		self._items: div.Children = None

	def render(self) -> div.Children: #type: ignore
		return self._items

	def __getitem__(self, values: div.Children):
		self._items = values
		return self

	# height of a div matches the height of all its children combined unless explicitly given
	def html_height(self) -> float:
		if self.height is not None:
			return self.height + self.css_padding_height

		height = 0.0
		for item in self.children:
			height += item.html_height()

		return height + self.css_padding_height

	# width of a div matches the width of its parent div unless explicitly given
	def html_width(self) -> float:
		if self.width is not None:
			return self.width + self.css_padding_width

		return max(self._available_block_width or 0, self.css_padding_width)

	def html_tag_and_attrbutes(self):
		attributes = f'id="{self.css_id}"' if self.css_id else ''
		tag = 'd'
		return (tag, attributes)

	def html(self) -> HtmlResponse:
		html = ''
		children_inline = False
		for item in self.children:
			children_inline = children_inline or item.is_inline

		if children_inline:
			from .align import aligned_html_inner
			html = aligned_html_inner(self)
		else:
			html = self.html_inner()

		h = self.html_height() - self.css_padding_height
		w = self.html_width() - self.css_padding_width
		offset= h / 2 - 0.5

		tag, attributes = self.html_tag_and_attrbutes()
		if children_inline:
			# this makes it so that divs with an img in them and divs without an img in them all align the same
			# and everything inside the div aligns vertically
			return f'<{tag} {attributes} style="height:{h:}rem; width:{w}rem; padding:{-offset}rem 0 {offset}rem 0"><img style="height:{h}rem">', html, f'</{tag}>'
		else:
			return f'<{tag} {attributes} style="height:{h}rem;width:{w}rem;">', html, f'</{tag}>'

def html_escape(text: str) -> str:
	return text.replace(" ", "\u00A0").replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;').replace('"', '&quot;').replace('\n', '\u00A0')

def html_escape_multi_line(text: str) -> str:
	return text.replace(" ", "\u00A0").replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;').replace('"', '&quot;').replace('\n', '<br>').replace('\t', '\u00A0\u00A0\u00A0')

class icon (span):
	def __init__(self, image: Image, width: float = 3, height: float = 3, padding: float = 0.5, align_left: bool = True, **kwargs: Unpack[SpanParams]) -> None:
		super().__init__(None, **kwargs)
		self.padding = padding
		self.image = image
		self.align_left = align_left

		self.width = width
		self.height = height

	def html(self) -> HtmlResponse:
		width = self.width - self.padding
		required_padding = self.padding
		tag, attributes = self.html_tag_and_attrbutes()
		top = 0.75
		if self.align_left:
			return f'<{tag} {attributes} style="position:relative;top:{top}rem;padding-right:{required_padding}rem;padding-top:{self.height-top}rem"><img style="width:{width}rem;height:{width}rem;" src="', self.image.data(self.layout), f'"></{tag}>'
		else:
			return f'<{tag} {attributes} style="position:relative;top:{top}rem;padding-left:{required_padding}rem;padding-top:{self.height-top}rem"><img style="width:{width}rem;height:{width}rem;" src="', self.image.data(self.layout), f'"></{tag}>'


class text (span, alignable):
	def __init__(self, text: str, css: css|None = None, **kwargs: Unpack[SpanParams]) -> None:
		super().__init__(css, **kwargs)
		self._text = text.replace("\u0000", "\\u0000")
		self._text_html = None

		self.align_required: int =  0
		self.align_desired: int = len(self._text)

	def align(self, width: float):
		self._text_html = None

		if width <= 0:
			self._text_clipped = ''
		elif len(self._text) > width:
			self._text_clipped = self._text[0: int(width-1)] + '…'
		else:
			self._text_clipped = self._text

		return len(self._text_clipped)

	def html_inner(self):
		if self._text_html is None:
			self._text_html = html_escape(self._text_clipped)
		return self._text_html


tokenize_re = re.compile('(0x[0-9A-Fa-f]+)|([-.0-9]+)|(\'[^\']*\')|("[^"]*")|(undefined|null)|(.*?)')

class code(span, alignable):
	def __init__(self, text: str, **kwargs: Unpack[SpanParams]) -> None:
		super().__init__(**kwargs)
		self.text = text.replace('\n', '\\n')
		self.text_html: str|None = None
		self.align_character_count = 0
		self.align_required: int = 0
		self.align_desired: int = len(self.text)

	def width(self) -> float:
		return len(self.text) + self.css_padding_width

	def align(self, width: float):
		self.text_html = None

		length = len(self.text)
		if width <= 0:
			self.align_character_count = 0
		elif length > width:
			self.align_character_count = width
		else:
			self.align_character_count = len(self.text)

		return self.align_character_count

	def html(self) -> HtmlResponse:
		if self.text_html:
			return self.text_html

		text_html = ''
		leftover = self.align_character_count

		def clip(value: str|None):
			if not value:
				return None

			nonlocal leftover
			if leftover <= 0:
				return None

			length = len(value)
			if leftover < length:
				leftover -= length
				return value[0: leftover -1] + '…'

			leftover -= length
			return value


		for number, number_hex, string, string_double, keyword, other in tokenize_re.findall(self.text):
			string = string_double or string
			number = number or number_hex
			if number := clip(number):
				text_html += f'<s style="color:var(--yellowish);">{number}</s>'
			elif string := clip(string):
				text_html += f'<s style="color:var(--greenish);">{html_escape(string)}</s>'
			elif keyword := clip(keyword):
				text_html += f'<s style="color:var(--redish);">{keyword}</s>'
			elif other := clip(other):
				text_html += html_escape(other)

		tag, attributes = self.html_tag_and_attrbutes()
		self.text_html = f'<{tag} {attributes}>{text_html}</{tag}>'
		return self.text_html
