
from .render import *
from .events import (
	GutterEvent,
	HoverEvent,
	ViewEventsListener,
	view_loaded,
	view_activated,
	view_text_hovered,
	view_gutter_hovered,
	view_gutter_double_clicked,
	view_selection_modified,
	view_modified,
	view_drag_select)

from .layout import *
from .component import *
from .image import *
from .segment import *
from .table import *
from .button import *
from .label import *
from .input import *
from .padding import *

import os

from sublime_debug.modules.libs import asyncio
from sublime_debug.modules import core


_update_timer = None #type: Optional[Timer]


def startup() -> None:
	Images.shared = Images()
	dir_path = os.path.dirname(os.path.abspath(__file__))
	import_css(dir_path + '/ui.css')

	global _update_timer
	_update_timer = Timer(update, 2, True)


def shutdown() -> None:
	if _update_timer:
		_update_timer.dispose()
	perform_render()
