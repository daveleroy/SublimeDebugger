from sublime_db.core.typecheck import (
	Tuple,
	Union,
	List,
	Optional,
	Callable,
	Sequence
)

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

	def added (self, layout: Layout) -> None:
		pass
	def removed(self) -> None:
		pass
	def on_focus(self) -> None:
		pass
	def on_unfocus(self) -> None:
		pass
			
	def render(self) -> components:
		return []

	def add_class(self, name: str) -> None:
		self.className += ' '
		self.className += name

	def dirty(self):
		if self.layout: self.layout.dirty()
		self.requires_render = True
		
	def html_inner(self, layout: Layout) -> str:
		html = []
		for child in self.children:
			html.append(child.html(layout))
		return ''.join(html)

	def html (self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		return '<{} class="{}" {}>{}</{}>'.format(self.html_tag, self.className, self.html_tag_extra, inner, self.html_tag)

class ComponentInline (Component):
	def __init__(self) -> None:
		super().__init__()
		self.html_tag = 'span'
	def html (self, layout: Layout) -> str:
		inner = self.html_inner(layout)
		return '<{} class="{}" {}><img class="height">{}</{}>'.format(self.html_tag, self.className, self.html_tag_extra, inner, self.html_tag)
