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
		self.render_items = [] #type: Sequence[Component]
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

	def render_dirty(self, layout: Layout) -> None:
		if self.requires_render:
			self.requires_render = False

			layout.remove_component_children(self)
			self.render_items = self.render()
			layout.add_component_children(self)
			
		for item in self.render_items:
			item.render_dirty(layout)

	def add_class(self, name: str) -> None:
		self.className += ' '
		self.className += name

	def dirty(self):
		self.requires_render = True
		if self.layout:
			self.layout.dirty()
		
	def html_inner(self, layout: Layout) -> str:
		html = []
		for item in self.render_items:
			html.append(item.html(layout))
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
