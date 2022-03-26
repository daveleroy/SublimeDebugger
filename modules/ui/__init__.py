from __future__ import annotations
from .. import core

from .phantom import Phantom, Popup

from .html import div, span, text, icon, click, code, html_escape
from .style import css

from .layout import Layout
from .image import Images, Image
from .input import *
from .align import align, spacer

from .debug import DEBUG_REFRESH


_update_timer: core.timer|None = None
_debug_force_update_timer: core.timer|None = None

def startup():
	Images.shared = Images()
	global _update_timer
	_update_timer = core.timer(Layout.update_layouts, 0.25, True)

	if DEBUG_REFRESH:
		global _debug_force_update_timer
		_debug_force_update_timer = core.timer(Layout.render_layouts, 1.0, True)


def shutdown():
	if _update_timer:
		_update_timer.dispose()
	if _debug_force_update_timer:
		_debug_force_update_timer.dispose()

	# perform one final render to clear up phantoms
	Layout.render_layouts()
