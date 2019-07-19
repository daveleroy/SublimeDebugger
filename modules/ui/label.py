from ..typecheck import *

from .layout import Layout
from .component import Inline, Block


html_escape_table = {
	"&": "&amp;",
	">": "&gt;",
	"<": "&lt;",
	" ": "\u2003" # HACK spaces inside <a> tags are not clickable. We replaces spaces with em spaces
}


def html_escape(text: str) -> str:
    """Produce entities within text."""
    return "".join(html_escape_table.get(c, c) for c in text)


class Label(Inline):
	def __init__(self, text: Optional[str], color: str = "primary", align: float = 0.5, width: Optional[float] = None, padding_left=0, padding_right=0) -> None:
		super().__init__()
		if text:
			self.text = text.replace("\u0000", "\\u0000")
		else:
			self.text = ""

		self.align = align
		self.width = width
		self.padding_left = padding_left
		self.padding_right = padding_right
		if color:
			self.add_class(color)
		self.render_text = ""

	def render(self) -> Inline.Children:
		layout = self.layout
		assert layout, '??'
		align = self.align
		max_size = self.width
		self.render_text = self.text
		if max_size:
			emWidth = layout.em_width()
			# give a bit of fuzz here otherwise setting width to em_width*chars might cut off a character
			max_characters = int((max_size + 0.001) / emWidth)
			self.render_text = self.render_text[0:max_characters]

			# calculate the padding we will need to add to align correctly
			leftover = self.width - (len(self.render_text) * emWidth)
			self.paddingleft = leftover * align
			self.paddingright = leftover * (1.0 - align)

		else:
			self.paddingright = 0
			self.paddingleft = 0

		self.paddingleft += self.padding_left
		self.paddingright += self.padding_right
		self.render_text = html_escape(self.render_text) or ""
		self.html_tag_extra = 'style="padding-left:{}rem; padding-right:{}rem;"'.format(self.paddingleft, self.paddingright)
		return []

	def html_inner(self, layout: Layout) -> str:
		return self.render_text


class CodeBlock(Inline):
	def __init__(self, text: str, language: str = 'c++') -> None:
		super().__init__()
		self.text = text
		self.language = language

	def added(self, layout: Layout) -> str:
		self.highlight = layout.syntax_highlight(self.text, self.language)

	def width(self, layout: Layout) -> float:
		return len(self.text) * layout.em_width()

	def html_inner(self, layout: Layout) -> str:
		return self.highlight.html or self.highlight.text
