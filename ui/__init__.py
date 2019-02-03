
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

import os

from sublime_db.libs import asyncio
from sublime_db import core


_rendering_timer = None #type: Optional[Timer]


def startup() -> None:
	Images.shared = Images()
	dir_path = os.path.dirname(os.path.abspath(__file__))
	import_css(dir_path + '/ui.css')

	# This really is only to catch the cases where the window is resized which invalidaes our layouts
	# It should probably be a seperate operation
	global _rendering_timer
	_rendering_timer = Timer(render, 1, True)


def shutdown() -> None:
	_rendering_timer.dispose()
	render()
