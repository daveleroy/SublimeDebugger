from ...import ui

button = ui.css(padding_left=1, padding_right=1, padding_top=0.7, padding_bottom=0.4, background_color='var(--segment-color)', raw='''
	border-radius: 0.75rem;
''')

label = ui.css(color='var(--primary)')
label_padding = ui.css(color='var(--primary)', padding_left=1, padding_right=1)

label_secondary = ui.css(color='var(--secondary)')
label_secondary_padding = ui.css(color='var(--secondary)', padding_left=1, padding_right=1)

label_redish = ui.css(color='var(--redish)')
label_redish_secondary = ui.css(color='color(var(--redish) alpha(0.7)')

padding = ui.css(padding_left=1, padding_right=1)


rounded_panel = ui.css(padding_top=1, padding_left=1, padding_right=1, background_color='var(--panel-color)', raw='''
	border-radius: 1rem;
''')

tab_panel = ui.css(padding_left=1, padding_right=8)
tab_panel_selected = ui.css(
	background_color='var(--panel-color)',
	padding_left=1,
	padding_right=8,
	raw='''
	position: relative;
	left: 1px;
	padding-bottom:1rem;
	border-top-left-radius: 1rem;
	border-top-right-radius: 1rem;
	'''
)

icon_sized_spacer = ui.css(padding_left=2.5)
table_inset = ui.css(padding_left=2)

selected = ui.css(background_color='color(var(--accent) alpha(0.2))', raw='border-radius:0.5rem;')
selected_text = ui.css(color='color(var(--accent) alpha(0.75))', padding_left=1, padding_right=1, raw='position: relative; top:-0.2rem;')

modified_label = ui.css(color='var(--secondary)', padding_left=3)
