from ..typecheck import *
from .. import core
from .. import ui 
from .. import dap
from ..debugger.breakpoints import Breakpoints
from ..debugger.watch import Watch, WatchView

from .variable_component import VariableStateful, VariableStatefulComponent
from .layout import variables_panel_width

import sublime

class VariablesPanel (ui.Block):
	def __init__(self, breakpoints: Breakpoints, watch: Watch) -> None:
		super().__init__()
		self.scopes = [] #type: List[dap.Scope]
		self.breakpoints = breakpoints
		self.watch = watch
		self.watch_view = WatchView(self.watch)
		watch.on_updated.add(self.dirty)
	
	def clear(self) -> None:
		self.scopes = []
		self.dirty()

	def set_scopes(self, scopes: List[dap.Scope]) -> None:
		self.scopes = scopes
		self.dirty()

	def on_edit_variable(self, variable: VariableStateful) -> None:
		core.run(self.on_edit_variable_async(variable))

	@core.coroutine
	def on_edit_variable_async(self, variable: VariableStateful) -> core.awaitable[None]:
		info = None #type: Optional[dap.DataBreakpointInfoResponse]
		try:
			info = yield from variable.variable.client.DataBreakpointInfoRequest(variable.variable)
		except dap.Error as e:
			pass


		expression = variable.variable.evaluateName or variable.variable.name
		value = variable.variable.value or ""

		def on_edit_variable(value: str):
			variable.set_value(value)

		def copy_value():
			sublime.set_clipboard(value)
		def copy_expr():
			sublime.set_clipboard(expression)
		def add_watch():
			self.watch.add(expression)
		
		items = [
			ui.InputListItem(
				ui.InputText (
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
				"Copy Value",
			),
			ui.InputListItem(
				add_watch,
				"Add Variable To Watch",
			),
		]
			
		if info and info.id:
			types = info.accessTypes or [""]
			labels = {
				dap.DataBreakpoint.write: "Break On Value Write",
				dap.DataBreakpoint.readWrite: "Break On Value Read or Write",
				dap.DataBreakpoint.read: "Break On Value Read",
			}
			def on_add_data_breakpoint(accessType: str):
				assert info
				self.breakpoints.data.add(info, accessType or None)

			for acessType in types:
				items.append(ui.InputListItem(
					lambda: on_add_data_breakpoint(acessType),
					labels.get(acessType) or "Break On Value Change"
				))

		ui.InputList(items).run()

	def render(self) -> ui.Block.Children:
		items = [
			self.watch_view
		] #type: List[ui.Block]

		scopes_items = [] #type: List[ui.Block]

		# expand the first scope only
		first = True
		for v in self.scopes:
			variable = dap.Variable(v.client, v.name, "", v.variablesReference)
			variable_stateful = VariableStateful(variable, None, on_edit=self.on_edit_variable)
			component = VariableStatefulComponent(variable_stateful)
			variable_stateful.on_dirty = component.dirty

			if first:
				first = False
				variable_stateful.expand()

			scopes_items.append(component)

		items.append(ui.Table(items=scopes_items))

		return items
