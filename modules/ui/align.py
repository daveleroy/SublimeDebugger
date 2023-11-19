from __future__ import annotations

from . import core
from . html import element, div, span, alignable

import math

class spacer (span):
	def __init__(self, width: float|None = None, min: float = 1):
		super().__init__()
		self.width = width
		if width is None:
			self.flex = True
			self.flex_width_min = min
		else:
			self.flex = False

	def required(self):
		if not self.flex:
			return self.width or 0

		return self.flex_width_min

	def resize(self, leftover: float) -> float:
		if not self.flex:
			return 0

		width = leftover + self.flex_width_min
		self.width = width
		return leftover

	def html(self, available_width: float, available_height: float) -> str:
		if self.width is None:
			core.error('flex width spacer was not aligned')

		# slight optmization for the most common case
		if self.width == 1:
			return '\u00A0'

		return f'<img style="width:{self.width or 0}rem">'


class spacer_dip (span):
	def __init__(self, width: float):
		super().__init__()
		self.width = width

	def required(self):
		return self.width/self.layout.em_width

	def html(self, available_width: float, available_height: float) -> str:
		return f'<img style="width:{self.width}px">'


def aligned_html_inner(item: div, available_width: float, available_height: float):
	width = int(available_width)

	# how much space was leftover that we can use to fill out any spacers
	leftover = width
	# how much space we need for items we can't resize
	required = 0

	resizeables: list[alignable] = []
	spacers: list[spacer] = []

	def calculate(item: element):
		nonlocal leftover
		nonlocal required

		if type(item) is spacer:
			w = item.required()
			leftover -= w
			required += w
			spacers.append(item)

		elif type(item) is spacer_dip:
			w = item.required()
			leftover -= w
			required += w

		elif isinstance(item, alignable):
			required += item.css_padding_width
			leftover -= item.css_padding_width
			required += item.align_required
			leftover -= item.align_desired
			resizeables.append(item)

		else:
			if item.width is None:
				required += item.css_padding_width
				leftover -= item.css_padding_width
				for i in item.children_rendered:
					calculate(i)
			else:
				w = item.width + item.css_padding_width
				leftover -= w
				required += w

	for i in item.children_rendered:
		calculate(i)

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
		w = min(max_width, element.align_desired) + element.align_required

		width_for_resizeables -= element.align(w)
		resizeables_left -= 1

	# Inline elements can be as tall as they want since they don't change the layout
	return item.html_inner(available_width, math.inf)
