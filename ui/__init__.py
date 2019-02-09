
from .render import * #type: ignore
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

from sublime_db.libs import asyncio
from sublime_db import core


_rendering_timer = None #type: Optional[Timer]


def startup() -> None:
	Images.shared = Images()
	dir_path = os.path.dirname(os.path.abspath(__file__))
	import_css(dir_path + '/ui.css')

	global _rendering_timer
	_rendering_timer = Timer(update, 2, True)


def shutdown() -> None:
	if _rendering_timer:
		_rendering_timer.dispose()
	render() #type: ignore
