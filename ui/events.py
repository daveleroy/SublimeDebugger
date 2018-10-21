
from debug.core.typecheck import (
	TypeVar, 
	Generic, 
	Callable, 
	List,
	Optional
)

import sublime 
import sublime_plugin

from debug import core

class GutterEvent:
	def __init__(self, view: sublime.View, line: int) -> None:
		self.view = view
		self.line = line

# all these events are dispatched from sublime's main thread to our own main loop
view_loaded = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]
view_activated = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]
view_gutter_hovered = core.EventDispatchMain() #type: core.EventDispatchMain[GutterEvent]
view_gutter_double_clicked = core.EventDispatchMain() #type: core.EventDispatchMain[GutterEvent]
view_selection_modified = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]
view_modified = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]
view_drag_select = core.EventDispatchMain() #type: core.EventDispatchMain[sublime.View]

class ViewEventsListener(sublime_plugin.EventListener):
	def __init__(self) -> None:
		self.was_drag_select = False

	# detects clicks on the gutter
	# if a click is detected we then reselect the previous selection
	# This means that a click in the gutter no longer selects that line
	def on_text_command(self, view: sublime.View, cmd: str, args: dict) -> None:
		print(cmd, args)
		if cmd == 'drag_select' and 'event' in args:
			view_drag_select.post(view)
			event = args['event']
			# left click
			if event['button'] != 1:
				return

			x = event['x']
			y = event['y']
			
			pt = view.window_to_text((x, y))
			on_gutter = _is_coord_on_gutter_or_empy_line(view, x, y)
			if not on_gutter:
				return
			self.line = view.rowcol(pt)[0]
			self.was_drag_select = True
			print('was drag select')

	def on_hover(self, view: sublime.View, point: int, hover_zone: int) -> None:
		if hover_zone == sublime.HOVER_GUTTER:
			line = view.rowcol(point)[0]
			print('on_gutter_hover: {}'.format(line))
			view_gutter_hovered.post(GutterEvent(view, line))

	def on_selection_modified(self, view: sublime.View) -> None:
		view_selection_modified.post(view)
		if self.was_drag_select:
			self.was_drag_select = False
			
			# if the selection is empty then they did not click on the gutter
			# a click on the gutter selects the full line
			# where as a click on an empty line puts the caret on that line
			s = view.sel()[0]
			l = view.full_line(view.text_point(self.line, 0))
			if s.a == 0 and s.b == view.size():
				print('on_gutter_double_clicked: {}'.format(self.line))
				view_gutter_double_clicked.post(GutterEvent(view, self.line))
				view.sel().clear()
				view.sel().add(view.line(view.text_point(self.line, 0)))
				
	def on_modified_async(self, view: sublime.View) -> None:
		view_modified.post(view)
	def on_load_async(self, view: sublime.View) -> None:
		view_loaded.post(view)
	def on_activated_async(self, view: sublime.View) -> None:
		view_activated.post(view)
		
def _is_coord_on_gutter_or_empy_line(view: sublime.View, x: int, y: int) -> bool:
	original_pt = view.window_to_text((x, y))
	if view.rowcol(original_pt)[1] != 0:
		return False
	adjusted_pt = view.window_to_text((x + int(view.em_width() / 2), y))
	if adjusted_pt != original_pt:
		return False
	return True
