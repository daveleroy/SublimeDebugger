from ..typecheck import *
from ..import dap
from ..import core
from ..import ui

class Modules:
	def __init__(self):
		self.modules = [] #type: List[dap.Module]
		self.on_updated = core.Event() #type: core.Event[None]

	def on_module_event(self, event: dap.ModuleEvent) -> None:
		if event.reason == dap.ModuleEvent.new:
			self.modules.append(event.module)
			self.on_updated()
			return
		if event.reason == dap.ModuleEvent.new:
			# FIXME: NOT IMPLEMENTED
			return
		if event.reason == dap.ModuleEvent.new:
			# FIXME: NOT IMPLEMENTED
			return

	def clear_session_date(self) -> None:
		self.modules.clear()
		self.on_updated()

class ModulesView(ui.Block):
	def __init__(self, modules: Modules):
		super().__init__()
		self.modules = modules

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.modules.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def render(self) -> ui.Panel.Children:
		items = []
		for module in self.modules.modules:
			items.append(
				ui.block(
					ui.Label(module.name)
				)
			)
		return [
			ui.Table(items=items)
		]
