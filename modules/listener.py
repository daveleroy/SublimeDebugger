from __future__ import annotations
from .typecheck import *

from .import core
from .import ui
from .import dap

from .project import Project
from .debugger import Debugger
from .breakpoints import Breakpoints, SourceBreakpoint
from .views.variable import VariableComponent

import sublime
import sublime_plugin
import re


def debuggers_for_view(view: sublime.View) -> Iterable[Debugger]:
	if window := view.window():
		if debugger := Debugger.get(window):
			return [debugger]

	return list(Debugger.instances.values())

def debugger_for_view(view: sublime.View) -> Debugger|None:
	if window := view.window():
		if debugger := Debugger.get(window):
			return debugger
	return None

def toggle_file_line(breakpoints: Breakpoints, file: str, line: int):
	bps = breakpoints.source.get_breakpoints_on_line(file, line)
	if bps:
		for bp in bps:
			breakpoints.source.remove(bp)
	else:
		breakpoints.source.add_breakpoint(file, line)

def edit_breakpoints_at_line(breakpoints: Breakpoints, source_breakpoints: list[SourceBreakpoint]):
	if not source_breakpoints:
		return

	if len(source_breakpoints) == 1:
		breakpoints.source.edit(source_breakpoints[0]).run()
		return

	items: list[ui.InputListItem] = []
	for breakpoint in source_breakpoints:
		items.append(
			ui.InputListItem(
				breakpoints.source.edit(breakpoint),
				"Breakpoint @ {}".format(breakpoint.tag),
			)
		)

	ui.InputList(items).run()


class Listener (sublime_plugin.EventListener):

	def ignore(self, view: sublime.View):
		return not bool(Debugger.instances)

	@core.schedule
	async def on_hover(self, view: sublime.View, point: int, hover_zone: int):
		if self.ignore(view): return

		debugger = debugger_for_view(view)
		if not debugger:
			return

		project = debugger.project
		sessions = debugger.sessions

		if hover_zone != sublime.HOVER_TEXT or not project.is_source_file(view):
			return

		if not sessions.has_active:
			return

		session = sessions.active

		r = session.adapter_configuration.on_hover_provider(view, point)
		if not r:
			return
		word_string, region = r

		try:
			response = await session.evaluate_expression(word_string, 'hover')
			await core.sleep(0.25)
			variable = dap.types.Variable("", response.result, response.variablesReference)
			view.add_regions('selected_hover', [region], scope="comment", flags=sublime.DRAW_NO_OUTLINE)

			def on_close() -> None:
				view.erase_regions('selected_hover')

			component = VariableComponent(dap.Variable(session, variable))
			component.toggle_expand()
			ui.Popup(ui.div(width=100)[component], view, region.a, on_close=on_close)

		# errors trying to evaluate a hover expression should be ignored
		except dap.Error as e:
			core.log_error("adapter failed hover evaluation", e)

	def on_text_command(self, view: sublime.View, cmd: str, args: dict) -> Any:
		if self.ignore(view): return

		if (cmd == 'drag_select' or cmd == 'context_menu') and 'event' in args:
			# on_view_drag_select_or_context_menu(view)

			event = args['event']
			x = event['x']
			y = event['y']

			view_x, view_y = view.layout_to_window(view.viewport_position()) #type: ignore

			margin = view.settings().get("margin") or 0
			offset = x - view_x

			if offset < -30 - margin:
				pt = view.window_to_text((x, y))
				line = view.rowcol(pt)[0]

				# only rewrite this command if someone actually consumed it
				# otherwise let sublime do its thing
				if self.on_view_gutter_clicked(view, line, event['button']):
					return ("null", {})

	def on_view_gutter_clicked(self, view: sublime.View, line: int, button: int) -> bool:
		line += 1 # convert to 1 based lines

		debuggers = debuggers_for_view(view)
		items = []

		for debugger in debuggers:
			breakpoints = debugger.breakpoints
			file = view.file_name()
			if not file:
				continue

			if button == 1:
				item = ui.InputListItem(
					run=lambda breakpoints=breakpoints, file=file: toggle_file_line(breakpoints, file, line),
					text=f'{debugger.project.name}: Toggle breakpoint'
				)
				items.append(item)

			elif button == 2:
				source_breakpoints = breakpoints.source.get_breakpoints_on_line(file, line)
				if not source_breakpoints:
					continue

				item = ui.InputListItem(
					run=lambda breakpoints=breakpoints, source_breakpoints=source_breakpoints: edit_breakpoints_at_line(breakpoints, source_breakpoints),
					text=f'{debugger.project.name}: Edit breakpoint'
				)
				items.append(item)

		if len(items) == 1:
			items[0].run()
		else:
			ui.InputList(items).run()

		# return true if we did something
		return bool(items)