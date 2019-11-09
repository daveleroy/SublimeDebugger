from ..typecheck import *

T = TypeVar('T')

class DiffCollection (Generic[T]):
	def __init__(self, on_added:Callable[[T], None], on_removed: Callable[[T], None]):
		self.items = [] # type: List[T]
		self.on_added = on_added
		self.on_removed = on_removed

	def update(self, new_items: List[T]):
		for item in self.items:
			if not item in new_items:
				self.on_removed(item)
				

		for new_item in new_items:
			if not new_item in self.items:
				self.on_added(new_item)

		self.items = list(new_items)
				
