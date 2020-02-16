from ...typecheck import *
from ...import ui

VARIABLE_PANEL_MIN_WIDTH = 50
PANEL_MIN_WIDTH = 75


def variables_panel_width(layout):
	view_width = layout.width()
	view_width -= 45
	used_width = VARIABLE_PANEL_MIN_WIDTH + PANEL_MIN_WIDTH
	unused_width = max(view_width - used_width, 0)
	return VARIABLE_PANEL_MIN_WIDTH + unused_width * 0.5


def pages_panel_width(layout):
	view_width = layout.width()
	view_width -= 45
	used_width = VARIABLE_PANEL_MIN_WIDTH + PANEL_MIN_WIDTH
	unused_width = max(view_width - used_width, 0)
	return PANEL_MIN_WIDTH + unused_width * 0.5


def breakpoints_panel_width(layout):
	return pages_panel_width(layout)


def console_panel_width(layout):
	return pages_panel_width(layout)


def callstack_panel_width(layout):
	return pages_panel_width(layout)
