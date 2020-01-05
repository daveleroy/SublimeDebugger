from ..typecheck import *
from . html import text, span
from . css import css


def text_align(width, values: Sequence[text]) -> span:
	items = [] #type: List[text]
	for text in values:
		css = text.css
		string = text.text
		if width < css.padding_width:
			return span()[items]

		width -= css.padding_width
		string = string[0:int(width)]
		width -= len(string)
		text.text = string
		items.append(text)

	return span()[items]
