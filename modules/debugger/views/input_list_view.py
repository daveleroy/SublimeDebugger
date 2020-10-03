
from ...import ui
from .import css

class InputListView (ui.div):
	def __init__(self, input: ui.InputList):
		super().__init__()
		self.input = input

	def render(self) -> ui.div.Children:
		items = []
		for input in self.input.values:
			text = input.text.split('\t')
			if len(text) == 1:
				text.append('')

			items.append(ui.div(height=css.row_height)[
				ui.click(lambda input=input: input.display_or_run())[
					ui.align()[
						ui.text(text[0], css=css.label_secondary),
						ui.spacer(),
						ui.text(text[1], css=css.button),
					]
				]
			])

		return items
