from ..import ui

line_height = 1.6
header_height = 4
row_height = 3
panel_padding= 2

button = ui.css(
	padding_left=1,
	padding_right=1,
	padding_top=-0.5,
	padding_bottom=-0.5,
	background_color='var(--segment-color)',
	color='var(--primary)',
	raw='border-radius: 0.4rem;'
)

button_secondary = ui.css(
	padding_left=1, 
	padding_right=1, 
	padding_top=-0.5, 
	padding_bottom=-0.5, 
	background_color='var(--segment-color)', 
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
	padding_top=1.5,
	padding_left=1.5,
	padding_right=1.5,
	background_color='var(--panel-color)',
	raw='''border-radius: 0.33rem;'''
)

panel = ui.css(
	padding_left=1.5,
	padding_right=1.5,
	background_color='var(--panel-color)',
)


tab_panel = ui.css(
	background_color='var(--panel-border)',
	padding_left=2,
	padding_right=2,
	raw='''
	padding-bottom: 0.33rem;
	border-top-left-radius: 0.33rem;
	border-top-right-radius: 0.33rem;
	'''
)

tab_panel_selected = ui.css(
	background_color='var(--panel-color)',
	padding_left=2,
	padding_right=2,
	raw='''
	padding-bottom: 1rem;
	border-top-left-radius: 0.33rem;
	border-top-right-radius: 0.33rem;
	'''
)

controls_panel = ui.css(
	background_color='var(--panel-color)',
	padding_left=1.5,
	padding_right=1.5,
	raw='''
	padding-bottom: 1rem;
	border-top-left-radius: 0.33rem;
	border-top-right-radius: 0.33rem;
	'''
)

table_inset = ui.css(
	padding_left=3
)

selected = ui.css(
	background_color='color(var(--accent) alpha(0.2))', 
	raw='border-radius:0.33rem;'
)
