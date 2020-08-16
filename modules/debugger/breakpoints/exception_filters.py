from ... typecheck import *
from ... import core
from ... import ui
from ..dap import types as dap


class ExceptionBreakpointsFilter:
	def __init__(self, dap: dap.ExceptionBreakpointsFilter, enabled: bool):
		self.dap = dap
		self.enabled = enabled

	@property
	def image(self) -> ui.Image:
		if self.enabled:
			return ui.Images.shared.dot
		else:
			return ui.Images.shared.dot_disabled

	@property
	def tag(self) -> Optional[str]:
		return None

	@property
	def name(self) -> str:
		return self.dap.label

	def into_json(self) -> dict:
		return {
			'dap': self.dap.into_json(),
			'enabled': self.enabled,
		}

	@staticmethod
	def from_json(json: dict) -> 'ExceptionBreakpointsFilter':
		return ExceptionBreakpointsFilter(
			dap.ExceptionBreakpointsFilter.from_json(json['dap']),
			json['enabled']
		)


class ExceptionBreakpointsFilters:
	def __init__(self) -> None:
		self.filters = {} #type: Dict[str, ExceptionBreakpointsFilter]
		self.on_updated = core.Event() #type: core.Event[Iterable[ExceptionBreakpointsFilter]]
		self.on_send = core.Event() #type: core.Event[Iterable[ExceptionBreakpointsFilter]]

	def __iter__(self):
		return iter(self.filters.values())

	def into_json(self) -> list:
		return list(map(lambda b: b.into_json(), self.filters.values()))

	def load_json(self, json: list):
		filters = list(map(lambda j: ExceptionBreakpointsFilter.from_json(j), json))
		self.filters = {}
		for filter in filters:
			self.filters[filter.dap.id] = filter
		self.on_updated(self.filters.values())

	def edit(self, breakpoint: ExceptionBreakpointsFilter):
		def toggle_enabled():
			self.toggle(breakpoint)

		return ui.InputList([
			ui.InputListItemChecked(
				toggle_enabled,
				"Enabled",
				"Disabled",
				breakpoint.enabled,
			),
		], placeholder='Edit Exception Filter {}'.format(breakpoint.name))

	def toggle(self, filter: ExceptionBreakpointsFilter):
		filter.enabled = not filter.enabled
		self.on_updated(self.filters.values())
		self.on_send(self.filters.values())

	def update(self, filters: List[dap.ExceptionBreakpointsFilter]):
		old = self.filters
		self.filters = {}
		for f in filters:
			if f.id in old:
				enabled = old[f.id].enabled
			else:
				enabled = f.default

			self.filters[f.id] = ExceptionBreakpointsFilter(f, enabled)

		self.on_updated(self.filters.values())
