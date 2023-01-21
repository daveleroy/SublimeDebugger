from __future__ import annotations

from . import core
from . html import element, div, span, alignable

import math

# spacers are integers so they can always undershoot the available space

class spacer (span):
	def __init__(self, width: int|None = None, min: int = 1):
		super().__init__()
		self._width = width

		if width is None:
			self.flex = True
			self.flex_width_min = min
		else:
			self.flex = False

	def required(self):
		if not self.flex:
			return self._width or 0

		return self.flex_width_min

	def resize(self, leftover: int) -> int:
		if not self.flex:
			return 0

		width = leftover + self.flex_width_min
		self._width = width
		return leftover

	def html(self) -> str:
		if self._width is None:
			core.error('flex width spacer was not aligned')

		# slight optmization for the most common case
		if self._width == 1:
			return '\u00A0'

		return f'<img style="width:{self._width or 0}rem">'


class spacer_dip (span):
	def __init__(self, width: int):
		super().__init__()
		self._width = width

	def width(self):
		return math.ceil(self._width/self.layout.em_width) # not ideal this might not match the actual width

	def html(self) -> str:
		return f'<img style="width:{self._width}px">'


def aligned_html_inner(item: div):
	width = int(item.width())
	# how much space was leftover that we can use to fill out any spacers
	leftover = width
	# how much space we need for items we can't resize
	required = 0

	resizeables = []
	spacers = []

	def calculate(item: element):
		nonlocal leftover
		nonlocal required

		if type(item) is spacer:
			w = item.required()
			leftover -= w
			required += w
			spacers.append(item)

		elif isinstance(item, alignable):
			required += int(item.css_padding_width)
			leftover -= int(item.css_padding_width)
			required += item.align_required
			leftover -= item.align_desired
			resizeables.append(item)

		elif type(item) is span:
			required += int(item.css_padding_width)
			leftover -= int(item.css_padding_width)
			for i in item.children:
				calculate(i)

		# don't look into any other items just use their width calculation...
		else:
			w = int(item.width())
			leftover -= w
			required += w

	for i in item.children:
		calculate(i)

	width_for_spacers = max(leftover, 0)
	width_for_resizeables = max(width - required, 0)

	def sort_by_align_desired(v):
		return v.align_desired

	resizeables.sort(key=sort_by_align_desired, reverse=False)

	for i in spacers:
		width_for_spacers -= i.resize(width_for_spacers)

	# divvy up the resizable space equally
	resizeables_left = len(resizeables)
	for i in resizeables:
		max_width = int(width_for_resizeables/resizeables_left)
		w = min(max_width, i.align_desired)
		i.align(w)
		width_for_resizeables -= w
		resizeables_left -= 1

	return item.html_inner()
