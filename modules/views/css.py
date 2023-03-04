from ..import ui

line_height = 1.6
header_height = 4
row_height = 3
panel_padding= 2

button = ui.css(
	padding_left=1,
	padding_right=1,
	padding_top=1.1,
	padding_bottom=0.9,
	background_color='var(--dark)',
	color='var(--primary)',
	raw='border-radius: 0.4rem;'
)

button_drop = ui.css(
	padding_left=1,
	padding_right=1,
	padding_top=1.3,
	padding_bottom=1.1,
	background_color='var(--tinted)',
	color='var(--primary)',
	raw='''
	position: relative;
	border-radius: 0.4rem;
	padding-right: 0.9rem;
	padding-left: 0.9rem;
	border-color: var(--dark);
	border-width: 0.1rem;
	border-style: solid;
	'''
)

button_secondary = ui.css(
	padding_left=1,
	padding_right=1,
	padding_top=1,
	padding_bottom=1,
	background_color='var(--dark)',
	color='var(--secondary)',
	raw='border-radius: 0.4rem;'
)

label = ui.css(
	color='var(--primary)'
)
label_secondary = ui.css(
	color='var(--secondary)'
)
label_placeholder = ui.css(
	color='color(var(--secondary) alpha(0.25)'
)
label_redish = ui.css(
	color='var(--redish)'
)
label_greenish = ui.css(
	color='var(--greenish)'
)
label_redish_secondary = ui.css(
	color='color(var(--redish) alpha(0.7)'
)
label_yellowish = ui.css(
	color='var(--yellowish)'
)
label_bluish = ui.css(
	color='var(--bluish)'
)

padding = ui.css(
	padding_left=0.5,
	padding_right=0.5
)

padding_left = ui.css(
	padding_left=1
)

rounded_panel = ui.css(
	padding_top=0.5,
	padding_left=1,
	padding_right=1,
	background_color='var(--tinted)',
	raw='''
		border-style: solid;
		border-top-width: 1px;
		border-color: var(--medium);
	'''
)

# these work around minor alignment issues where inline phantoms and bottom phantoms do not align the same
console_tabs_bottom = ui.css(
	raw='''
		padding-left: 2px;
	'''
)
console_tabs_top = ui.css(
	raw='''
		padding-left: -3px;
	'''
)

seperator = ui.css(
	raw='''
		border-style: solid;
		border-top-width: 1px;
		border-color: var(--medium);
		padding-top: 0px;
	'''
)
seperator_cutout = ui.css(
	background_color='var(--background)',
	raw='''
		position: relative;
		top: -0.5rem;
		right: -30rem;
		padding-top: 1rem;
	'''
)

panel = ui.css(
	padding_left=1,
	padding_right=1,
	padding_top=0.5,
	background_color='var(--tinted)',
	raw='''
		border-style: solid;
		border-top-width: 1px;
		border-color: var(--medium);
	'''
)


tab = ui.css(
	background_color='var(--light)',
	padding_left=2,
	padding_right=2,
	padding_top= 2,
	padding_bottom=2,
	raw='''
	border-top-left-radius: 0.33rem;
	border-top-right-radius: 0.33rem;
	'''
)

tab_selected = ui.css(
	background_color='var(--medium)',
	padding_left=2,
	padding_right=2,
	padding_top= 2,
	padding_bottom=2,
	raw='''
	border-top-left-radius: 0.33rem;
	border-top-right-radius: 0.33rem;
	'''
)

tab_spacer = ui.css(
	background_color='var(--redish)',
	raw='''
	border-top-left-radius: 0.33rem;
	border-top-right-radius: 0.33rem;
	padding-bottom: 25px;
	margin-bottom: 25px;
	'''
)

controls_panel = ui.css(
	background_color='var(--light)',
	padding_left=1,
	padding_right=1,
	padding_top= 2,
	padding_bottom=2,
	raw='''
	border-top-right-radius: 0.33rem;
	border-top-left-radius: 0.33rem;
	'''
)

table_inset = ui.css(
	padding_left=3
)

selected = ui.css(
	background_color='color(var(--accent) alpha(0.2))',
	raw='border-radius:0.33rem;'
)
