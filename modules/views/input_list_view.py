from __future__ import annotations

from ..import ui
from .import css

class InputListView (ui.div):
	def __init__(self, input: ui.InputList):
		super().__init__()
		self.input = input

	def render(self):
		items: list[ui.div] = []
		for input in self.input.values:
			items.append(ui.div(height=css.row_height)[
				ui.click(lambda input=input: input.display_or_run())[
					ui.align()[
						ui.text(input.text, css=css.label_secondary),
						ui.spacer(),
						ui.text(input.annotation, css=css.button),
					]
				]
			])

		return items
