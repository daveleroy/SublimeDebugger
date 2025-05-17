from __future__ import annotations
from .. import core

from .phantom import Phantom, Html, RawPhantom, RawAnnotation, Popup

from .html import div, span, text, icon, code, html_escape, html_escape_multi_line
from .align import alignable, spacer, spacer_dip
from .css import css

from .layout import Layout
from .image import Images, Image
from .input import *


_update_timer: core.timer | None = None
_debug_force_update_timer: core.timer | None = None


def startup():
	Images.shared = Images()
	global _update_timer
	_update_timer = core.timer(Layout.update_layouts, 0.2, True)


def update_and_render(invalidate=False):
	if invalidate:
		for r in Layout.layouts:
			r.invalidate()

	Layout.update_layouts()
	Layout.render_layouts()


def shutdown():
	if _update_timer:
		_update_timer.dispose()
	if _debug_force_update_timer:
		_debug_force_update_timer.dispose()

	if Popup.current:
		Popup.current.dispose()

	# perform one final render to clear up phantoms
	Layout.render_layouts()

