from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from .layout import Layout

import sublime

class css:
	next_id = 1
	instances = []

	_cached_css: dict[str, str] = {}
	_variables_css = ''
	_base_css = '''
	a {
		text-decoration: none;
		color: var(--foreground);
	}
	s {
		color: var(--foreground);
	}
	d {
		display: block;
	}
	i {
		display: inline-block;
	}
	'''
	# for debugging purposes
	# d {
	# 	background-color: color(red alpha(0.1));

	# 	--panel-color: color(red alpha(0.25));
	# 	--segment-color: color(red alpha(0.25));
	# 	--panel-border: color(red alpha(0.25));
	# }
	# s {
	# 	background-color: color(blue alpha(0.15));

	# 	--tinted: color(blue alpha(0.25));
	# 	--light: color(blue alpha(0.25));
	# 	--medium: color(blue alpha(0.25));
	# 	--dark: color(blue alpha(0.25));

	# 	padding-top: 0.5rem;
	# 	padding-bottom: 0.5rem;
	# }

	# a {
	# 	background-color: color(green alpha(0.25));

	# 	--tinted: color(green alpha(0.25));
	# 	--light: color(green alpha(0.25));
	# 	--medium: color(green alpha(0.25));
	# 	--dark: color(green alpha(0.25));

	# 	padding-top: 0.5rem;
	# 	padding-bottom: 0.5rem;
	# }

	# '''

	@staticmethod
	def variables(dark: dict[str, str], light: dict[str, str]):
		style = ''
		style += '.dark {\n'
		for color, value in dark.items():
			style += f'--{color}: {value};'
		style += '}\n'

		style += '.light {\n'
		for color, value in light.items():
			style += f'--{color}: {value};'
		style += '}\n'

		css._variables_css = style
		css.invalidate()

	@staticmethod
	def invalidate():
		css._cached_css.clear()

	@staticmethod
	def generate(layout: Layout):
		key = f'{layout.em_width}-{layout.font_size}-{layout.internal_font_scale}'
		if c := css._cached_css.get(key):
			return c

		css_list = [css._base_css, css._variables_css]

		# rem units are based on character width now. 1 rem = 1 character width
		css_list.append(f'html {{ font-size: {layout.em_width}px; line-height: 0; }}')

		# Change the font-size back since we changed the font-size in the html tag for the rem units
		# I have no idea why windows/linux needs pt instead of px to get the font-size correct...
		if sublime.platform() == 'osx':
			css_list.append(f'body {{ font-size: {layout.font_size * layout.internal_font_scale}px; }}')
		else:
			css_list.append(f'body {{ font-size: {layout.font_size * layout.internal_font_scale}pt; }}')

		for c in css.instances:
			css_list.append('#{}{{'.format(c.id))
			if not c.height is None:
				css_list.append(f'height:{c.height}rem;')
			if not c.width is None:
				css_list.append(f'width:{c.width}rem;')
			if not c.padding_top is None:
				css_list.append(f'padding-top:{c.padding_top}rem;')
			if not c.padding_bottom is None:
				css_list.append(f'padding-bottom:{c.padding_bottom}rem;')
			if not c.padding_left is None:
				css_list.append(f'padding-left:{c.padding_left}rem;')
			if not c.padding_right is None:
				css_list.append(f'padding-right:{c.padding_right}rem;')
			if not c.background_color is None:
				css_list.append(f'background-color:{c.background_color};')
			if not c.color is None:
				css_list.append(f'color:{c.color};')
			if not c.radius is None:
				css_list.append(f'border-radius:{c.radius}rem;')
			if not c.raw is None:
				css_list.append(c.raw)

			css_list.append('}')

		css_string = ''.join(css_list)
		css._cached_css[key] = css_string
		return css_string

	def __init__(
		self,
		raw: str|None = None,
		width: float|None = None,
		height: float|None = None,
		padding_top: float|None = None,
		padding_bottom: float|None = None,
		padding_left: float|None = None,
		padding_right: float|None = None,
		radius: float|None = None,
		background_color: str|None = None,
		color: str|None = None,
	):

		self.raw = raw
		self.width = width
		self.height = height
		self.padding_top = padding_top
		self.padding_bottom = padding_bottom
		self.padding_left = padding_left
		self.padding_right = padding_right
		self.radius = radius
		self.background_color = background_color
		self.color = color

		self.id = '_{}'.format(css.next_id)
		css.next_id += 1

		css.instances.append(self)

		additional_width = 0.0
		additional_height = 0.0

		if not height is None:
			additional_height += height
		if not width is None:
			additional_width += width
		if not padding_top is None:
			additional_height += padding_top
		if not padding_bottom is None:
			additional_height += padding_bottom
		if not padding_left is None:
			additional_width += padding_left
		if not padding_right is None:
			additional_width += padding_right

		self.padding_height = additional_height
		self.padding_width = additional_width
