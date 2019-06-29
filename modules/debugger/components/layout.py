from sublime_debug.modules.core.typecheck import (
	Callable,
	Any,
	List,
	Sequence,
	Tuple
)

from sublime_debug.modules import ui

VARIABLE_PANEL_MIN_WIDTH = 40
PANEL_MIN_WIDTH = 65
PANEL_CONTENT_MAX_WIDTH = 60


def variables_panel_width(layout):
	view_width = layout.width()
	view_width -= 6
	used_width = VARIABLE_PANEL_MIN_WIDTH + PANEL_MIN_WIDTH
	unused_width = view_width - used_width
	return VARIABLE_PANEL_MIN_WIDTH + unused_width * 0.66


def pages_panel_width(layout):
	view_width = layout.width()
	view_width -= 6
	used_width = VARIABLE_PANEL_MIN_WIDTH + PANEL_MIN_WIDTH
	unused_width = view_width - used_width
	return PANEL_MIN_WIDTH + unused_width * 0.33


def breakpoints_panel_width(layout):
	return pages_panel_width(layout)


def console_panel_width(layout):
	return pages_panel_width(layout)


def callstack_panel_width(layout):
	return pages_panel_width(layout)
