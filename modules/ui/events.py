from .. typecheck import *
from .. import core

import sublime
import sublime_plugin

class GutterEvent:
	def __init__(self, view: sublime.View, line: int, button: int = 0) -> None:
		self.view = view
		self.line = line
		self.button = button


class HoverEvent:
	def __init__(self, view: sublime.View, point: int) -> None:
		self.view = view
		self.point = point


# all these events are dispatched from sublime's main thread to our own main loop
view_loaded = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]
view_activated = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]
view_text_hovered = core.EventDispatchMain() #type: core.EventDispatchMain[HoverEvent]
view_gutter_hovered = core.EventDispatchMain() #type: core.EventDispatchMain[GutterEvent]
view_gutter_clicked = core.EventDispatchMain() #type: core.EventDispatchMain[GutterEvent]
view_selection_modified = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]
view_modified = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]
view_drag_select = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]


class ViewEventsListener(sublime_plugin.EventListener):

	# detects clicks on the gutter
	# if a click is detected we then reselect the previous selection
	# This means that a click in the gutter no longer selects that line
	def on_text_command(self, view: sublime.View, cmd: str, args: dict) -> None:
		if (cmd == 'drag_select' or cmd == 'context_menu') and 'event' in args:
			event = args['event']

			view_x, view_y = view.layout_to_window(view.viewport_position())

			x = event['x']
			y = event['y']

			margin = view.settings().get("margin")
			offset = x - view_x

			view.window().run_command("hide_overlay")
			if offset < -30 - margin:
				pt = view.window_to_text((x, y))
				line = view.rowcol(pt)[0]
				view_gutter_clicked.post(GutterEvent(view, line, event['button']))
				return ("null", {})

	def on_hover(self, view: sublime.View, point: int, hover_zone: int) -> None:
		if hover_zone == sublime.HOVER_GUTTER:
			line = view.rowcol(point)[0]
			view_gutter_hovered.post(GutterEvent(view, line))
		elif hover_zone == sublime.HOVER_TEXT:
			view_text_hovered.post(HoverEvent(view, point))

	def on_modified(self, view: sublime.View) -> None:
		view_modified.post(view)

	def on_load(self, view: sublime.View) -> None:
		view_loaded.post(view)

	def on_activated(self, view: sublime.View) -> None:
		view_activated.post(view)

