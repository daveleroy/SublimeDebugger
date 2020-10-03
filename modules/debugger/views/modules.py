from ...typecheck import *
from ...import core
from ...import ui

from ..import dap
from . import css

import sublime

class ModulesView(ui.div):
	def __init__(self, sessions: dap.Sessions):
		super().__init__()
		self.sessions = sessions
		self.expanded = {} #type: Dict[Any, bool]

	def added(self, layout: ui.Layout):
		self.on_updated_modules = self.sessions.on_updated_modules.add(self.updated)
		self.on_removed_session = self.sessions.on_removed_session.add(self.updated)

	def updated(self, session: dap.Session):
		self.dirty()

	def removed(self):
		self.on_updated_modules.dispose()
		self.on_removed_session.dispose()

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
		for session in self.sessions:
			items.append(ui.div(height=css.row_height)[
				ui.text(session.name)
			])

			for module in session.modules.values():
				is_expanded = self.is_expanded(module)
				image_toggle = ui.Images.shared.open if is_expanded else ui.Images.shared.close
				item = ui.div(height=css.row_height)[
					ui.align()[
						ui.click(lambda module=module: self.toggle_expanded(module))[ #type: ignore
							ui.icon(image_toggle),
						],
						ui.text(module.name)
					]
				]
				items.append(item)
				if is_expanded:
					body = []
					def add_item(label, value):
						if value is None:
							return

						def copy():
							ui.InputList([
								ui.InputListItem(lambda: sublime.set_clipboard(value), "Copy")
							], value).run()

						value_str = str(value)
						body.append(
							ui.div(height=3)[
								ui.align()[
									ui.click(copy)[
										ui.text(label, css=css.label_secondary_padding),
										ui.spacer(1),
										ui.text(value_str, css=css.label),
									]
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
