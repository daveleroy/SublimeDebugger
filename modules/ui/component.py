from ..typecheck import *

from .layout import Layout

components = Sequence['Component']


class Component:
	def __init__(self) -> None:
		self.layout = None #type: Optional[Layout]
		self.children = [] #type: Sequence[Component]
		self.className = self.__class__.__name__
		self.html_tag = 'div'
		self.html_tag_extra = ''
		self.requires_render = True
		self.is_focus = False

	def added(self, layout: Layout) -> None:
		pass

	def removed(self) -> None:
		pass

	def on_focus(self) -> None:
		pass

	def on_unfocus(self) -> None:
		pass

	def render(self) -> components:
		return []

	def height(self, layout: Layout) -> float:
		max = 0.0
		for item in self.children:
			h = item.height(layout)
			if h > max:
				max = h
		return max

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
		inner = self.html_inner(layout)
		height = self.height(layout)
		if height != 0:
			return '<{} class="{}" style="height:{}rem;"{}>{}</{}>'.format(self.html_tag, self.className, self.height(layout), self.html_tag_extra, inner, self.html_tag)
		return '<{} class="{}" {}>{}</{}>'.format(self.html_tag, self.className, self.html_tag_extra, inner, self.html_tag)


class Inline (Component):
	Children = Sequence['Inline']

	def __init__(self) -> None:
		super().__init__()
		self.html_tag = 'span'

	def render(self) -> Sequence['Inline']:
		return []

	def height(self, layout: Layout) -> float:
		from .size import HEIGHT
		max = HEIGHT
		for item in self.children:
			h = item.height(layout)
			if h > max:
				max = h
		return max

	def html(self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		return '<{} class="{}" {}>{}</{}>'.format(self.html_tag, self.className, self.html_tag_extra, inner, self.html_tag)


class Block (Component):
	Children = Sequence['Block']

	def render(self) -> Sequence['Block']:
		return []

	def height(self, layout: Layout) -> float:
		total = 0.0
		for item in self.children:
			h = item.height(layout)
			total += h
		return total

	def html(self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		return '<{} class="{}" style="height:{}rem;"{}>{}</{}>'.format(self.html_tag, self.className, self.height(layout), self.html_tag_extra, inner, self.html_tag)


class BlockInline (Block):
	Children = Sequence['Inline']

	def __init__(self, items: Sequence['Inline']) -> None:
		super().__init__()
		self.html_tag = 'div'
		self.items = items
	
	def render(self) -> Sequence['Inline']:  #type: ignore
		return self.items

	def height(self, layout: Layout) -> float:
		from .size import HEIGHT
		max = HEIGHT
		for item in self.children:
			h = item.height(layout)
			if h > max:
				max = h
		return max

	def html(self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		return '<{} class="{}" style="height:{}rem;"{}><img class="height">{}</{}>'.format(self.html_tag, self.className, self.height(layout), self.html_tag_extra, inner, self.html_tag)


def block(*items: Inline) -> Block:
	return BlockInline(items)
