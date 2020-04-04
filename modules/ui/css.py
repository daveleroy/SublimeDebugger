from .. typecheck import *

CHARACTER_SIZE_REM = 1.6

base_css = '''
html {
}
body {
	padding-top: 1px;
}
.dark {
	--panel-color: color(var(--background) blend(black 90%));
	--segment-color: color(var(--background) blend(black 75%));

	--text-color: var(--foreground);
	--label-color: var(--text-color);

	--primary: var(--text-color);
	--secondary: color(var(--text-color) alpha(0.7));
}
.light {
	--panel-color: color(var(--background) blend(black 92%));
	--segment-color: color(var(--background) blend(black 87%));

	--text-color: var(--foreground);
	--label-color: var(--text-color);

	--primary: var(--text-color);
	--secondary: color(var(--text-color) alpha(0.7));
}
span {
}
div {
}
a {
	text-decoration: none;
}
'''

class css:
	all = base_css
	id = 0

	def __init__(
		self,
		raw: Optional[str] = None,
		padding_top: Optional[float] = None,
		padding_bottom: Optional[float] = None,
		padding_left: Optional[float] = None,
		padding_right: Optional[float] = None,
		background_color: Optional[str] = None,
		color: Optional[str] = None,
	):

		self.id = css.id
		css.id += 1

		self.class_name = '_{}'.format(self.id)

		css_string = '.{} {{'.format(self.class_name)

		additional_width = 0.0
		additional_height = 0.0

		if not padding_top is None:
			css_string += 'padding-top:{}rem;'.format(padding_top/CHARACTER_SIZE_REM)
			additional_height += padding_top
		if not padding_bottom is None:
			css_string += 'padding-bottom:{}rem;'.format(padding_bottom/CHARACTER_SIZE_REM)
			additional_height += padding_bottom
		if not padding_left is None:
			css_string += 'padding-left:{}rem;'.format(padding_left/CHARACTER_SIZE_REM)
			additional_width += padding_left
		if not padding_right is None:
			css_string += 'padding-right:{}rem;'.format(padding_right/CHARACTER_SIZE_REM)
			additional_width += padding_right
		if not background_color is None:
			css_string += 'background-color:{};'.format(background_color)
		if not color is None:
			css_string += 'color:{};'.format(color)
		if not raw is None:
			css_string += raw

		css_string += '}'
		css.all += css_string

		self.padding_height = additional_height
		self.padding_width = additional_width


div_inline_css = css(
	padding_top=-1.0,
	padding_bottom=1.0
)

none_css = css()

icon_css = css(raw='''
	position: relative;
	top:0.5rem;
	line-height:0;
''')
