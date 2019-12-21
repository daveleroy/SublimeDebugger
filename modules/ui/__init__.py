from .. import core

from .render import *
from .events import (
	GutterEvent,
	HoverEvent,
	ViewEventsListener,
	view_loaded,
	view_activated,
	view_text_hovered,
	view_gutter_hovered,
	view_gutter_clicked,
	view_selection_modified,
	view_modified,
	view_drag_select)

from .html import div, span, text, icon, click, code
from .css import css

from .layout import *
from .component import *
from .image import *
from .input import *

import os

from ..libs import asyncio


_update_timer = None #type: Optional[Timer]


def startup() -> None:
	Images.shared = Images()
	global _update_timer
	_update_timer = Timer(update, 2, True)


def shutdown() -> None:
	if _update_timer:
		_update_timer.dispose()
	perform_render()
