
from debug.core.typecheck import (
	List,
	Optional,
	Callable,
)

#for mypy
if False: from .component import Component

from .layout import Layout

import sublime

_phantoms = [] #type: List[Phantom]
_phantoms_remove = [] #type: List[Phantom]
_phantoms_add = [] #type: List[Phantom]

def render () -> None:
	requires_updated_set = False
	_phantoms.extend(_phantoms_add)
	
	for p in _phantoms_remove:
		_phantoms.remove(p)
		p.clear_phantom_set()

	_phantoms_add.clear()
	_phantoms_remove.clear()

	phantoms_to_update = [] #type: List[Phantom]
	for p in _phantoms:
		p.render_dirty()
		if p.requires_updated_set:
			phantoms_to_update.append(p)

	if not phantoms_to_update:
		return
		
	# after we generated the html we need to to update the sublime phantoms
	# if we don't do this on the sublime main thread we get flickering
	def on_sublime_thread() -> None:
		for p in phantoms_to_update:
			p.update_phantom_set_if_needed()

	sublime.set_timeout(on_sublime_thread, 0)

class Phantom(Layout):
	def __init__(self, component: 'Component', view: sublime.View, region: sublime.Region, layout: int = sublime.LAYOUT_INLINE) -> None:
		super().__init__(component)
		self.cachedPhantom = None #type: Optional[sublime.Phantom]
		self.region = region
		self.layout = layout
		self.view = view
		self.set = sublime.PhantomSet(self.view) #type: Optional[sublime.PhantomSet]
		self.requires_updated_set = False
		_phantoms_add.append(self)
	def render_dirty(self) -> None:
		if self.render() or not self.cachedPhantom:
			html = '''<body id="debug"><style>{}</style>{}</body>'''.format(self.css, self.html)
			self.cachedPhantom = sublime.Phantom(self.region, html, self.layout, self.on_navigate)
			self.requires_updated_set = True
			#print(html)
	def update_phantom_set_if_needed(self) -> None:
		if not self.requires_updated_set:
			return

		assert self.set, '??'
		assert self.cachedPhantom, "??"
		self.set.update([self.cachedPhantom])
		self.requires_updated_set = False

	def clear_phantom_set(self) -> None:
		assert self.set, '??'
		assert self.cachedPhantom, "??"
		self.set.update([])
		self.requires_updated_set = False

	def em_width(self) -> float:
		size = self.view.settings().get('font_size')
		assert size
		return self.view.em_width() / size

	def dispose(self) -> None:
		super().dispose()
		_phantoms_remove.append(self)


