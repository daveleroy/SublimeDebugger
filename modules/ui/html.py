from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Generator, Sequence, TypedDict, Union
from ..core.typing import Unpack

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
		self.layout: Layout = None #type: ignore
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

	def render(self) -> Children:
		return self._items

	def __getitem__(self, values: Children):
		self._items = values
		return self

	def html_tag_and_attrbutes(self, layout: Layout):
		attributes = f'id="{self.css_id}"'
		tag = 's'

		if on_click := self.kwargs.get('on_click'):
			tag = 'a'
			id = layout.register_on_click_handler(on_click)
			attributes += f' href="{id}"'

		if title := self.kwargs.get('title'):
			attributes += f' title="{title}"'

		return (tag, attributes)

	def html(self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		tag, attributes = self.html_tag_and_attrbutes(layout)
		return f'<{tag} {attributes}>{inner}</{tag}>'


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
			children_inline = children_inline or item.is_inline

		if children_inline:
			from .align import aligned_html_inner
			html = aligned_html_inner(self, layout)
		else:
			html = self.html_inner(layout)

		h = self.height(layout) - self.padding_height
		w = self.width(layout) - self.padding_width
		offset= h / 2 - 0.5
		if children_inline:
			# this makes it so that divs with an img in them and divs without an img in them all align the same
			# and everything inside the div aligns vertically
			return f'<d id="{self.css_id}" style="height:{h}rem; width:{w}rem; padding:{-offset}rem 0 {offset}rem 0"><img style="height:{h}rem">{html}</d>'
		else:
			return f'<d id="{self.css_id}" style="height:{h}rem;width:{w}rem;">{html}</d>'

def html_escape(text: str) -> str:
	return text.replace(" ", "\u00A0").replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;').replace('"', '&quot;').replace('\n', '\u00A0')

def html_escape_multi_line(text: str) -> str:
	return text.replace(" ", "\u00A0").replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;').replace('"', '&quot;').replace('\n', '<br>').replace('\t', '\u00A0\u00A0\u00A0')

class text (span, alignable):
	def __init__(self, text: str, css: css|None = None, **kwargs: Unpack[SpanParams]) -> None:
		super().__init__(css, **kwargs)
		self._text = text.replace("\u0000", "\\u0000")
		self._text_clipped = self._text
		self._text_html = None

		self.align_required: int = 0
		self.align_desired: int = len(self._text)

	def align(self, width: int):
		if len(self._text) > width:
			self._text_clipped = self._text[0:int(width-1)] + '…'
			self._text_html = None

	def width(self, layout: Layout) -> float:
		return len(self._text_clipped) + self.padding_width

	def html_inner(self, layout: Layout):
		if self._text_html is None:
			self._text_html = html_escape(self._text_clipped)
		return self._text_html

class icon (span):
	def __init__(self, image: Image, width: float = 3, height: float = 3, padding: float = 0.5, align_left: bool = True, **kwargs: Unpack[SpanParams]) -> None:
		super().__init__(None, **kwargs)
		self.padding = padding
		self.image = image
		self.align_left = align_left

		self._width = width
		self._height = height

	def html(self, layout: Layout) -> str:
		assert self._height
		width = self._height - self.padding
		required_padding = self.padding
		tag, attributes = self.html_tag_and_attrbutes(layout)
		top = 0.75
		if self.align_left:
			return f'<{tag} {attributes} style="position:relative;top:{top}rem;padding-right:{required_padding:.2f}rem;"><img style="width:{width:.2f}rem;height:{width:.2f}rem;" src="{self.image.data(layout)}"></{tag}>'
		else:
			return f'<{tag} {attributes} style="position:relative;top:{top}rem;padding-left:{required_padding:.2f}rem;"><img style="width:{width:.2f}rem;height:{width:.2f}rem;" src="{self.image.data(layout)}"></{tag}>'


tokenize_re = re.compile('(0x[0-9A-Fa-f]+)|([-.0-9]+)|(\'[^\']*\')|("[^"]*")|(.*?)')


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
		
		