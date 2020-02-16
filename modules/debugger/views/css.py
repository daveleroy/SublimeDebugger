from ...import ui


line_height = 1.6
header_height = 3
row_height = 3

button = ui.css(padding_left=1, padding_right=1, padding_top=0.3, padding_bottom=0.3, background_color='var(--segment-color)', raw='''
	border-radius: 0.5rem;
''')

label = ui.css(color='var(--primary)')
label_padding = ui.css(color='var(--primary)', padding_left=0.75, padding_right=0.75)

label_secondary = ui.css(color='var(--secondary)')
label_secondary_padding = ui.css(color='var(--secondary)', padding_left=0.75, padding_right=0.75)

label_redish = ui.css(color='var(--redish)')
label_redish_secondary = ui.css(color='color(var(--redish) alpha(0.7)')

padding = ui.css(padding_left=0.75, padding_right=0.75)


rounded_panel = ui.css(padding_top=0.75, padding_left=0.75, padding_right=0.75, background_color='var(--panel-color)', raw='''
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
	padding-bottom:2rem;
	border-top-left-radius: 0.75rem;
	border-top-right-radius: 0.75rem;
	'''
)

icon_sized_spacer = ui.css(padding_left=1.6*1.6)
table_inset = ui.css(padding_left=2)

selected = ui.css(background_color='color(var(--accent) alpha(0.2))', raw='border-radius:0.5rem;')
selected_text = ui.css(color='color(var(--accent) alpha(0.75))', padding_left=1, padding_right=1, raw='position: relative; top:-0.2rem;')

modified_label = ui.css(color='var(--secondary)', padding_left=3)
