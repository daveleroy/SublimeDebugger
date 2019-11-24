from .. typecheck import *
from .. import ui
from .. import core
from .. import dap

from . import css

import sublime


class VariableReference (Protocol):
	@property
	def client(self) -> dap.Client: 
		...
	@property
	def name(self) -> str: 
		...
	@property
	def value(self) -> str: 
		...
	@property
	def variablesReference(self) -> int:
		...

class EvaluateVariable:
	def __init__(self, client: dap.Client, name: str, response: dap.EvaluateResponse):
		self.response = response
		self.client = client
		self._name = name

	@property
	def variablesReference(self) -> int:
		return self.response.variablesReference
	@property
	def name(self) -> str:
		return self._name
	@property
	def value(self) -> str:
		return self.response.result

class VariableStateful:
	def __init__(self, variable: VariableReference, on_dirty: Callable[[], None], on_edit: Optional[Callable[['VariableStateful'], None]] = None) -> None:
		self.variable = variable
		self.on_dirty = on_dirty
		self.on_edit = on_edit
		self._expanded = False
		self.fetched = False
		self.loading = False
		self.variables = [] #type: List[VariableStateful]
		self.expandedCount = 0

	@property
	def name(self) -> str:
		return self.variable.name

	@property
	def value(self) -> str:
		return self.variable.value

	@property
	def expanded(self) -> bool:
		return self._expanded

	@property
	def expandable(self) -> bool:
		return self.variable.variablesReference != 0

	def toggle_expand(self) -> None:
		if self._expanded:
			self._expanded = False
			self.expandedCount = 0
		else:
			self._expanded = True
			self.expandedCount = 20
			self._fetch_if_needed()
		self.on_dirty()

	def expand(self) -> None:
		if not self._expanded:
			self.toggle_expand()

	def show_more(self) -> None:
		self.expandedCount += 20
		self.on_dirty()

	def number_expanded(self) -> int:
		return min(len(self.variables), self.expandedCount)

	def has_more(self) -> int:
		if self.expandedCount >= len(self.variables):
			return 0
		return len(self.variables) - self.expandedCount

	def collapse(self) -> None:
		if self._expanded:
			self.toggle_expand()

	@core.coroutine
	def _set_value(self, value: str) -> core.awaitable[None]:
		try:
			variable = yield from self.variable.client.setVariable(self.variable, value)
			self.variable = variable
			if self.fetched:
				self._fetch_if_needed(True)
			self.on_dirty()

		except Exception as e:
			core.log_exception()
			core.display(e)

	def set_value(self, value: str) -> None:
		core.run(self._set_value(value))

	def _fetch_if_needed(self, force_refetch: bool = False) -> None:
		if (not self.fetched or force_refetch) and self.variable.variablesReference:
			self.loading = True
			core.run(self.variable.client.GetVariables(self.variable.variablesReference), self._on_fetched)

	def _on_fetched(self, variables: List[dap.Variable]) -> None:
		self.fetched = True
		self.loading = False
		self.variables = []
		for variable in variables:
			self.variables.append(VariableStateful(variable, self.on_dirty, self.on_edit))

		self.on_dirty()


class VariableStatefulComponent (ui.div):
	def __init__(self, variable: VariableStateful, syntax_highlight=True, itemRight: Optional[ui.span] = None) -> None:
		super().__init__()
		self.syntax_highlight = syntax_highlight
		self.variable = variable
		self.itemRight = itemRight or ui.span()

	def on_edit(self) -> None:
		if self.variable.on_edit:
			self.variable.on_edit(self.variable)

	def render(self) -> ui.div.Children:
		v = self.variable
		name = v.name
		value = v.value

		value_item = ui.click(self.on_edit)[
			ui.text(name, css=css.label_secondary_padding),
			ui.code(value) if self.syntax_highlight else ui.text(value),
		]

		if not self.variable.expandable:
			return [
				ui.div(height=3.0, width=100, css=css.icon_sized_spacer)[
					value_item,
					self.itemRight
				],
			]

		variable_label = ui.div(height=3.0, width=100, css=css.icon_sized_spacer)[
			ui.click(self.variable.toggle_expand)[
				ui.icon(ui.Images.shared.open if self.variable.expanded else ui.Images.shared.close)
			],
			value_item,
			self.itemRight
		]

		if not self.variable.expanded:
			return [
				variable_label
			]

		variable_children = [] #type: List[ui.div]
		count = self.variable.number_expanded()
		syntax_highlight = count < 25
		for variable in self.variable.variables[:count]:
			variable_children.append(VariableStatefulComponent(variable, syntax_highlight))

		more_count = self.variable.has_more()
		if more_count:
			variable_children.append(
				ui.div(height=3.0)[
					ui.click(self.variable.show_more,)[
						ui.text("  {} more items...".format(more_count), css=css.label_secondary)
					]
				]
			)

		return [
			variable_label,
			ui.div(css=css.table_inset)[
				variable_children
			]
		]
