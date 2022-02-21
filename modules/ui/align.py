from __future__ import annotations
from ..typecheck import *

from . html import span, click, alignable
from . layout import Layout

# spacers are integers so they can always undershoot the available space

class spacer (span):
	def __init__(self, width: int|None = None, min: int|None = None):
		super().__init__(width, None, None)
		self.flex_width = width
		self.flex_width_min = min

	def required(self):
		if self.flex_width is not None:
			return self.flex_width

		if self.flex_width_min is not None:
			return self.flex_width_min

		return 0

	def resize(self, leftover: int) -> int:
		if self.flex_width is not None:
			return 0

		width = leftover + (self.flex_width_min or 0)
		self._width = width
		self.flex_width = width
		return leftover

	def html(self, layout: Layout) -> str:
		assert self.flex_width
		return '\u00A0' * self.flex_width


class align (span):
	def __init__(self, priority: float = 1.0):
		super().__init__()
		self.flex_priority = priority

	def html(self, layout: Layout):
		elements = self.children
		width = int(self.width(layout) * self.flex_priority)

		# how much space was leftover that we can use to fill out any spacers
		leftover = width
		# how much space we need for items we can't resize
		required = 0

		resizeables = []
		spacers = []

		def calculate(element):
			nonlocal leftover
			nonlocal required

			if type(element) == spacer:
				w = element.required()
				leftover -= w
				required += w
				spacers.append(element)

			elif isinstance(element, alignable):
				required += int(element.css.padding_width)
				leftover -= int(element.css.padding_width)
				required += element.align_required
				leftover -= element.align_desired
				resizeables.append(element)

			elif type(element) == span or type(element) == click:
				required += int(element.css.padding_width)
				leftover -= int(element.css.padding_width)
				for element in element.children or []:
					calculate(element)

			# don't look into any other elements just use their width calculation...
			else:
				w = int(element.width(layout))
				leftover -= w
				required += w

		for element in elements:
			calculate(element)

		width_for_spacers = max(leftover, 0)
		width_for_resizeables = max(width - required, 0)

		def sort_by_align_desired(v):
			return v.align_desired

		resizeables.sort(key=sort_by_align_desired, reverse=False)

		for element in spacers:
			width_for_spacers -= element.resize(width_for_spacers)

		# divvy up the resizable space equally
		resizeables_left = len(resizeables)
		for element in resizeables:
			max_width = int(width_for_resizeables/resizeables_left)
			w = min(max_width, element.align_desired)
			element.align(w)
			width_for_resizeables -= w
			resizeables_left -= 1

		return self.html_inner(layout)
