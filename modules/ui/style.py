from __future__ import annotations
from .. typecheck import *

from .debug import DEBUG_DRAW

if TYPE_CHECKING:
	from .layout import Layout

base_css = '''
.dark {
	--panel-border: color(var(--background) blend(black 97%));
	--panel-color: color(var(--background) blend(black 91%));
	--segment-color: color(var(--background) blend(black 75%));

	--text-color: var(--foreground);
	--label-color: var(--text-color);

	--primary: var(--text-color);
	--secondary: color(var(--text-color) alpha(0.7));
}
.light {
	--panel-color: color(var(--background) blend(black 97%));
	--panel-border: color(var(--background) blend(black 92%));
	--segment-color: color(var(--background) blend(black 92%));

	--text-color: var(--foreground);
	--label-color: var(--text-color);

	--primary: var(--text-color);
	--secondary: color(var(--text-color) alpha(0.7));
}
a {
	text-decoration: none;
}
d {
	display: block;
}
l {
	display: inline-block;
}
'''


if DEBUG_DRAW:
	base_css += '''
d {
	background-color: color(red alpha(0.1));

	--panel-color: color(red alpha(0.25));
	--segment-color: color(red alpha(0.25));
	--panel-border: color(red alpha(0.25));

	--text-color: var(--foreground);
	--label-color: var(--text-color);

	border-style: solid;
	border-color: black;
	border-width: 0.15px;
}
s {
	background-color: color(blue alpha(0.15));

	--panel-color: color(blue alpha(0.25));
	--segment-color: color(blue alpha(0.25));

	--text-color: var(--foreground);
	--label-color: var(--text-color);

	border-style: solid;
	border-color: black;
	border-width: 0.15px;
}

l {
	background-color: color(green alpha(0.25));
	--panel-color: color(green alpha(0.25));
	--segment-color: color(green alpha(0.25));

	--text-color: var(--foreground);
	--label-color: var(--text-color);
}

'''

class css:
	id = 0
	instances = []

	@staticmethod
	def generate(layout: Layout):
		css_string = base_css
		for c in css.instances:
			css_string += '#{}{{'.format(c.css_id)
			if not c.height is None:
				css_string += 'height:{}rem;'.format(layout.to_rem(c.height))
			if not c.width is None:
				css_string += 'width:{}rem;'.format(layout.to_rem(c.width))
			if not c.padding_top is None:
				css_string += 'padding-top:{}rem;'.format(layout.to_rem(c.padding_top))
			if not c.padding_bottom is None:
				css_string += 'padding-bottom:{}rem;'.format(layout.to_rem(c.padding_bottom))
			if not c.padding_left is None:
				css_string += 'padding-left:{}rem;'.format(layout.to_rem(c.padding_left))
			if not c.padding_right is None:
				css_string += 'padding-right:{}rem;'.format(layout.to_rem(c.padding_right))
			if not c.background_color is None:
				css_string += 'background-color:{};'.format(c.background_color)
			if not c.color is None:
				css_string += 'color:{};'.format(c.color)
			if not c.radius is None:
				css_string += 'border-radius:{}rem;'.format(layout.to_rem(c.radius))
			if not c.raw is None:
				css_string += c.raw

			css_string += '}'
		
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

		self.id = css.id
		css.id += 1

		self.css_id = '_{}'.format(self.id)

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



none_css = css()

icon_css = css(raw='''
	position: relative;
	top:0.5rem;
	line-height:0;
''')
