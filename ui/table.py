from sublime_db.core.typecheck import (
	List,
	Sequence,
	Optional
)
from .component import Component


class TableItem (Component):
	def __init__(self, items: List[Component]) -> None:
		super().__init__()
		self.items = items

	def render(self) -> Sequence[Component]:
		return self.items


class Table (Component):
	def __init__(self, items: Optional[Sequence[Component]] = None, table_items: Optional[Sequence[TableItem]] = None, selected_index=-1) -> None:
		super().__init__()
		self.selected_index = selected_index
		if not items is None:
			assert table_items is None, 'expecting table_items to be None if items is set'
			new_items = [] #type: List[TableItem]
			for index, item in enumerate(items):
				item = TableItem(items=[item])
				if selected_index == index:
					item.add_class('selected')
				new_items.append(item)
			self.items = new_items #type: Sequence[TableItem]
		if not table_items is None:
			assert items is None, 'expecting items to be None if table_items is set'
			self.items = table_items

	def render(self) -> Sequence[Component]:
		return self.items
