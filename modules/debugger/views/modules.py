from ...typecheck import *
from ...import dap
from ...import core
from ...import ui

from ..debugger_session import Modules

from . import css


class ModulesView(ui.div):
	def __init__(self, modules: Modules):
		super().__init__()
		self.modules = modules
		self.expanded = {} #type: Dict[Any, bool]

	def added(self, layout: ui.Layout):
		self.on_updated_handle = self.modules.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated_handle.dispose()

	def is_expanded(self, module: dap.Module) -> bool:
		return self.expanded.get(module.id, False)

	def toggle_expanded(self, module: dap.Module):
		if self.is_expanded(module):
			self.expanded[module.id] = False
		else:
			self.expanded[module.id] = True

		self.dirty()

	def render(self) -> ui.div.Children:
		items = []
		for module in self.modules.modules:
			is_expanded = self.is_expanded(module)
			image_toggle = ui.Images.shared.open if is_expanded else ui.Images.shared.close
			item = ui.div(height=css.row_height)[
				ui.click(lambda module=module: self.toggle_expanded(module))[ #type: ignore
					ui.icon(image_toggle),
				],
				ui.text(module.name)
			]
			items.append(item)
			if is_expanded:
				body = []
				def add_item(label, value):
					if value is None:
						return

					def copy():
						import sublime
						ui.InputList([
							ui.InputListItem(lambda: sublime.set_clipboard(value), "Copy")
						], value).run()

					value_str = str(value)
					body.append(
						ui.div(height=3)[
							ui.click(copy)[
								ui.text(label, css=css.label_secondary_padding),
								ui.text(value_str, css=css.label),
							]
						]
					)

				add_item('path', module.path)
				add_item('symbols', module.symbolStatus)
				add_item('symbol file path', module.symbolFilePath)
				add_item('load address', module.addressRange)

				items.append(ui.div(css=css.table_inset)[
					body
				])

		return [
			ui.div()[
				items
			]
		]
