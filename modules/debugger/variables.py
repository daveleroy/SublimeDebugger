from ..typecheck import *
from ..import core
from ..import dap
from ..import ui
from .views import css

import sublime
import dataclasses
import os

if TYPE_CHECKING:
	from .debugger_session import DebuggerSession

class VariableReference (Protocol):
	@property
	def name(self) -> str:
		...
	@property
	def value(self) -> str:
		...
	@property
	def variablesReference(self) -> int:
		...

class EvaluateReference:
	def __init__(self, name: str, response: dap.EvaluateResponse):
		self._response = response
		self._name = name
	@property
	def variablesReference(self) -> int:
		return self._response.variablesReference
	@property
	def name(self) -> str:
		return self._name
	@property
	def value(self) -> str:
		return self._response.result

class ScopeReference:
	def __init__(self, scope: dap.Scope):
		self.scope = scope
	@property
	def variablesReference(self) -> int:
		return self.scope.variablesReference
	@property
	def name(self) -> str:
		return self.scope.name
	@property
	def value(self) -> str:
		return ""

class Variable:
	def __init__(self, session: 'DebuggerSession', reference: VariableReference) -> None:
		self.session = session
		self.reference = reference
		self.fetched = None #type: Optional[core.future]

	@property
	def name(self) -> str:
		return self.reference.name

	@property
	def value(self) -> str:
		return self.reference.value

	async def fetch(self):
		variables = await self.session.client.GetVariables(self.reference.variablesReference)
		return [Variable(self.session, v) for v in variables]

	async def children(self) -> List['Variable']:
		if not self.has_children:
			return []

		if not self.fetched:
			self.fetched = core.run(self.fetch())
		children = await self.fetched
		return children

	@property
	def has_children(self) -> bool:
		return self.reference.variablesReference != 0


class Variables:
	def __init__(self):
		self.variables = [] #type: List[Variable]
		self.on_updated = core.Event() #type: core.Event

	def update(self, session: 'DebuggerSession', scopes: List[dap.Scope]):
		self.variables = [Variable(session, ScopeReference(scope)) for scope in scopes]
		self.on_updated()

	def clear_session_data(self):
		self.variables.clear()
		self.on_updated()

@dataclasses.dataclass
class Source:
	source: dap.Source
	line: Optional[int] = None
	column: Optional[int] = None

	@staticmethod
	def from_path(file, line, column) -> 'Source':
		return Source(dap.Source(os.path.basename(file), file), line, column)

	@property
	def name(self) -> str:
		if self.column and self.line:
			return f'{self.source.name}@{self.line}:{self.column}'
		if self.line:
			return f'{self.source.name}@{self.line}'

		return self.source.name or "??"

class VariableComponentState:
	def __init__(self):
		self._expanded = {}
		self._number_expanded = {}

	def is_expanded(self, variable: Variable) -> bool:
		return self._expanded.get(id(variable), False)

	def set_expanded(self, variable: Variable, value: bool):
		self._expanded[id(variable)] = value

	def number_expanded(self, variable: Variable) -> int:
		return self._number_expanded.get(id(variable), 20)

	def set_number_expanded(self, variable: Variable, value: int):
		self._number_expanded[id(variable)] = value


class VariableComponent (ui.div):
	def __init__(self, variable: Variable, source: Optional[Source] = None, on_clicked_source: Optional[Callable[[Source], None]] = None, state=VariableComponentState()) -> None:
		super().__init__()
		self.variable = variable
		self.state = state
		self.item_right = ui.span()
		self.variable_children: List[Variable] = []
		self.edit_variable_menu = None
		self.on_clicked_source = on_clicked_source
		self.source = source

		if self.state.is_expanded(self.variable):
			self.set_expanded()

	@core.schedule
	async def edit_variable(self) -> None:
		if not isinstance(self.variable.reference, dap.Variable):
			raise core.Error("Not able to set value of this item")

		variable = self.variable.reference
		session = self.variable.session
		info = None #type: Optional[dap.DataBreakpointInfoResponse]
		expression = variable.evaluateName or variable.name
		value = variable.value or ""

		if session.capabilities.supportsDataBreakpoints:
			info = await session.client.DataBreakpointInfoRequest(variable)

		async def on_edit_variable_async(value: str):
			try:
				self.variable.reference = await session.client.setVariable(variable, value)
				self.variable.fetched = None
				self.dirty()
			except core.Error as e:
				core.log_exception()
				core.display(e)

		def on_edit_variable(value: str):
			core.run(on_edit_variable_async(value))

		def copy_value():
			sublime.set_clipboard(value)

		def copy_expr():
			sublime.set_clipboard(expression)

		def add_watch():
			session.watch.add(expression)

		items = [
			ui.InputListItem(
				ui.InputText(
					on_edit_variable,
					"editing a variable",
				),
				"Edit Variable",
			),
			ui.InputListItem(
				copy_expr,
				"Copy Expression",
			),
			ui.InputListItem(
				copy_value,
				"Copy Value\t Click again to select",
			),
			ui.InputListItem(
				add_watch,
				"Add Variable To Watch",
			),
		]

		if self.edit_variable_menu:
			copy_value()
			self.edit_variable_menu.cancel()
			return

		if info and info.id:
			types = info.accessTypes or [""]
			labels = {
				dap.DataBreakpoint.write: "Break On Value Write",
				dap.DataBreakpoint.readWrite: "Break On Value Read or Write",
				dap.DataBreakpoint.read: "Break On Value Read",
			}

			def on_add_data_breakpoint(accessType: str):
				assert info
				session.breakpoints.data.add(info, accessType or None)

			for acessType in types:
				items.append(ui.InputListItem(
					lambda: on_add_data_breakpoint(acessType),
					labels.get(acessType) or "Break On Value Change"
				))
		self.edit_variable_menu = ui.InputList(items, '{} {}'.format(variable.name, variable.value)).run()
		await self.edit_variable_menu
		self.edit_variable_menu = None

	@core.schedule
	async def set_expanded(self) -> None:
		self.state.set_expanded(self.variable,True)
		self.variable_children = await self.variable.children()
		self.dirty()

	@core.schedule
	async def toggle_expand(self) -> None:
		self.state.set_expanded(self.variable, not self.state.is_expanded(self.variable))
		self.variable_children = await self.variable.children()
		self.dirty()

	def show_more(self) -> None:
		count = self.state.number_expanded(self.variable)
		self.state.set_number_expanded(self.variable, count + 20)
		self.dirty()

	def render(self) -> ui.div.Children:
		v = self.variable
		width = self.width(self.layout)
		width -= css.icon_sized_spacer.padding_width

		name =  v.name[0:int(width)]
		if name:
			name += " "
			width -= len(name)

		value = v.value[0:int(width)]
		width -= len(value)

		if self.source:
			source = self.source.name[0:int(width - 1)]

		if name:
			value_item = ui.click(self.edit_variable)[
				ui.text(name, css=css.label_secondary),
				ui.code(value),
			]
		else:
			value_item = ui.click(self.edit_variable)[
				ui.code(value),
			]
		if self.source and width > 0:
			print(width)
			self.item_right = ui.click(lambda: self.on_clicked_source(self.source))[
				ui.text(source.rjust(int(width)), css=css.label_secondary)
			]
		if not self.variable.has_children:
			return [
				ui.div(height=css.row_height, width=100, css=css.icon_sized_spacer)[
					value_item,
					self.item_right
				],
			]

		is_expanded = self.state.is_expanded(self.variable)

		variable_label = ui.div(height=css.row_height, width=100)[
			ui.click(self.toggle_expand)[
				ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close)
			],
			value_item,
			self.item_right
		]

		if not is_expanded:
			return [
				variable_label
			]

		variable_children = [] #type: List[ui.div]
		count = self.state.number_expanded(self.variable)
		for variable in self.variable_children[:count]:
			variable_children.append(VariableComponent(variable, state=self.state))

		more_count = len(self.variable_children) - count
		if more_count > 0:
			variable_children.append(
				ui.div(height=css.row_height)[
					ui.click(self.show_more)[
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
