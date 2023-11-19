from __future__ import annotations
from typing import Any, Iterable

from ..import core
from ..import ui
from ..import dap

class ExceptionBreakpointsFilter:
	def __init__(self, dap: dap.ExceptionBreakpointsFilter, enabled: bool = True, condition: str|None = None):
		self.dap = dap
		self.enabled = enabled
		self.condition = condition

	@property
	def image(self) -> ui.Image:
		if not self.enabled:
			return ui.Images.shared.dot_disabled
		elif self.condition:
			return ui.Images.shared.dot_expr
		else:
			return ui.Images.shared.dot

	@property
	def tag(self) -> str|None:
		return None

	@property
	def name(self) -> str:
		return self.dap.label

	@property
	def description(self) -> str|None:
		return self.dap.description

	def into_json(self) -> core.JSON:
		return core.JSON({
			'dap': self.dap,
			'enabled': self.enabled,
			'condition': self.condition
		})

	@staticmethod
	def from_json(json: core.JSON) -> 'ExceptionBreakpointsFilter':
		return ExceptionBreakpointsFilter(
			json['dap'],
			json['enabled'],
			json.get('condition')
		)

class ExceptionBreakpointsFilters:
	def __init__(self) -> None:
		self.filters: dict[str, ExceptionBreakpointsFilter] = {}
		self.on_updated = core.Event[Iterable[ExceptionBreakpointsFilter]]()
		self.on_send = core.Event[Iterable[ExceptionBreakpointsFilter]]()

	def __iter__(self):
		return iter(self.filters.values())

	def into_json(self) -> list[Any]:
		return list(map(lambda b: b.into_json(), self.filters.values()))

	def load_json(self, json: list[Any]):
		filters = list(map(lambda j: ExceptionBreakpointsFilter.from_json(j), json))
		self.filters = {}
		for filter in filters:
			self.filters[filter.dap.filter] = filter
		self.on_updated(self.filters.values())

	def edit(self, breakpoint: ExceptionBreakpointsFilter, index=1):
		def toggle_enabled():
			self.toggle_enabled(breakpoint)
			self.edit(breakpoint, index=1).run()

		def set_condition(text: str):
			self.set_condition(breakpoint, text)
			self.edit(breakpoint, index=0).run()

		items: list[ui.InputListItem] = [ui.InputListItemChecked(
			toggle_enabled,
			breakpoint.enabled,
			'Enabled',
			'Disabled',
		)]

		if breakpoint.dap.supportsCondition:
			items.insert(0, ui.InputListItemCheckedText(
				set_condition,
				'Condition',
				breakpoint.dap.conditionDescription or 'Breaks when expression is true',
				breakpoint.condition,
			))
		return ui.InputList('Edit Exception Filter {}'.format(breakpoint.name), index=index)[
			items
		]

	def toggle_enabled(self, filter: ExceptionBreakpointsFilter):
		filter.enabled = not filter.enabled
		self.on_updated(self.filters.values())
		self.on_send(self.filters.values())

	def set_condition(self, filter: ExceptionBreakpointsFilter, condition: str|None):
		filter.condition = condition
		self.on_updated(self.filters.values())
		self.on_send(self.filters.values())

	def update(self, filters: list[dap.ExceptionBreakpointsFilter]):
		old = self.filters
		self.filters = {}
		for f in filters:
			if f.filter in old:
				filter_old = old[f.filter]
				enabled = filter_old.enabled
				condition = filter_old.condition if f.supportsCondition else None
			else:
				enabled = f.default or False
				condition = None

			self.filters[f.filter] = ExceptionBreakpointsFilter(f, enabled, condition)

		self.on_updated(self.filters.values())
