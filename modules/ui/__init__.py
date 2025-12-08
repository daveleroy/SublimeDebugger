from __future__ import annotations
from typing import Type, TypeVar, cast

import sublime

from .. import core

from .phantom import Phantom, Html, RawPhantom, RawAnnotation, Popup
from .view import View, ViewRegistry
from .html import div, span, text, icon, code, html_escape, html_escape_multi_line
from .align import alignable, spacer, spacer_dip
from .css import css

from .image import Images, Image
from .input import *


_update_timer: core.timer | None = None
_debug_force_update_timer: core.timer | None = None


def startup(debug: bool):
	ViewRegistry.debug = debug
	Images.shared = Images()
	global _update_timer
	_update_timer = core.timer(ViewRegistry.update_layouts, 0.2, True)


def update_and_render(invalidate=False):
	if invalidate:
		for r in ViewRegistry.layouts:
			r.invalidate()

	ViewRegistry.update_layouts()
	ViewRegistry.render_layouts()


T = TypeVar('T')


def element_at_layout_position(view: sublime.View, position: tuple[float, float], type: Type[T]):
	if layout := ViewRegistry.view_at_position(view, position):
		element = layout.element_at_layout_position(position, type)
		if element:
			return cast(T, element)
	return None

def shutdown():
	if _update_timer:
		_update_timer.dispose()
	if _debug_force_update_timer:
		_debug_force_update_timer.dispose()

	if Popup.current:
		Popup.current.dispose()

	# perform one final render to clear up phantoms
	ViewRegistry.render_layouts()

