from sublime_db.core.typecheck import (
	Any,
	Callable,
	Optional
)

import sublime
import sublime_plugin

from sublime_db import core
from sublime_db import ui
from sublime_db.main.breakpoints import Breakpoints, Breakpoint, FunctionBreakpoint
from .commands import AutoCompleteTextInputHandler

def edit_breakpoint(breakpoints: Breakpoints, breakpoint: Breakpoint, selected_index = 0):
	if isinstance(breakpoint, Breakpoint):
		edit_line_breakpoint(breakpoints, breakpoint, selected_index)
	elif isinstance(breakpoint, FunctionBreakpoint):
		edit_function_breakpoint(breakpoints, breakpoint, selected_index)
	else:
		assert False, "expected Breakpoint or FunctionBreakpoint"
def edit_line_breakpoint(breakpoints: Breakpoints, breakpoint: Breakpoint, selected_index = 0):
	window = sublime.active_window()
	core.run(open_file_and_hightlight(window, breakpoint.file, breakpoint.line-1))
	cancel_select_async = open_file_and_cancel_highlight(window, breakpoint.file, breakpoint.line-1)

	values = []
	values.append(ListInputItemChecked("Expr", breakpoint.condition, "Breaks when expression is true"))
	values.append(ListInputItemChecked("Log", breakpoint.log, "Message to log, expressions within {} are interpolated"))
	values.append(ListInputItemChecked("Count", breakpoint.count, "Break when hit count condition is met"))
	values.append(ui.ListInputItem(["○ Disabled", "● Disabled"][not breakpoint.enabled]))
	values.append(ui.ListInputItem("    Remove"))
	input = ui.ListInput(values, placeholder="Edit breakpoint @ line {}".format(breakpoint.line), index=selected_index)

	def run_main(**args):
		core.run(cancel_select_async)
		i = args['list']
		if i == 4:
			breakpoints.remove_breakpoint(breakpoint)
			return

		if i == 0:
			breakpoints.set_breakpoint_condition(breakpoint, args['text'])
		if i == 1:
			breakpoints.set_breakpoint_log(breakpoint, args['text'])
		if i == 2:
			breakpoints.set_breakpoint_count(breakpoint, args['text'])
		if i == 3:
			breakpoints.set_breakpoint_enabled(breakpoint, not breakpoint.enabled)
		
		edit_line_breakpoint(breakpoints, breakpoint, i)
		
	def on_cancel():
		core.run(cancel_select_async)
	ui.run_input_command(input, run_main, on_cancel=on_cancel)

def edit_function_breakpoint(breakpoints: Breakpoints, breakpoint: FunctionBreakpoint, selected_index = 0):
	values = []
	values.append(ListInputItemChecked("Expr", breakpoint.condition, "Breaks when expression is true"))
	values.append(ListInputItemChecked("Count", breakpoint.hitCondition, "Break when hit count condition is met"))
	values.append(ui.ListInputItem(["○ Disabled", "● Disabled"][not breakpoint.enabled]))
	values.append(ui.ListInputItem("    Remove"))
	input = ui.ListInput(values, placeholder="Edit breakpoint @ function {}".format(breakpoint.name), index=selected_index)

	def run_main(**args):
		i = args['list']
		if i == 3:
			breakpoints.remove_breakpoint(breakpoint)
			return

		if i == 0:
			breakpoints.set_breakpoint_condition(breakpoint, args['text'])
		if i == 1:
			breakpoints.set_breakpoint_count(breakpoint, args['text'])
		if i == 2:
			breakpoints.set_breakpoint_enabled(breakpoint, not breakpoint.enabled)
		
		edit_function_breakpoint(breakpoints, breakpoint, i)
		
	ui.run_input_command(input, run_main)

class ListInputItemChecked (ui.ListInputItem):
	def __init__(self, name, initial, placeholder):
		text = ""
		if initial: text += '● '
		else: text += '○ '
		text += name
		if initial:
			text += ": "
			text += initial
		elif placeholder:
			text += ": "
			text += placeholder

		next_input = ui.TextInput(
			initial=initial,
			placeholder=placeholder
		)
		super().__init__(text, name, next_input)


@core.async
def open_file_and_hightlight(window, file, line):
	view = yield from core.sublime_open_file_async(window, file, line-1)
	print('sel')
	view.sel().clear()
	rl = view.line(view.text_point(line, 0))
	view.add_regions("debug.add_breakpoint", [sublime.Region(rl.a, rl.a)], scope="markup.deleted",flags=sublime.DRAW_SOLID_UNDERLINE|sublime.DRAW_NO_FILL|sublime.DRAW_NO_OUTLINE|sublime.DRAW_EMPTY)
	
@core.async
def open_file_and_cancel_highlight(window, file, line):
	view = yield from core.sublime_open_file_async(window, file, line-1)
	view.erase_regions("debug.add_breakpoint")

def add_breakpoint(breakpoints: Breakpoints, file: str, line: int, selected_index = 0):
	window = sublime.active_window()
	core.run(open_file_and_hightlight(window, file, line-1))
	cancel_select_async = open_file_and_cancel_highlight(window, file, line-1)
	values = []
	values.append(ui.ListInputItem("Add breakpoint"))
	input = AutoCompleteTextInputHandler("name of function to break on")
	values.append(ui.ListInputItem("Add function breakpoint", name="function name", next_input=input))
	input = ui.ListInput(values, placeholder="Add breakpoint @ line {}".format(line), index=selected_index)

	def run_main(**args):
		print(args)
		i = args['list']
		if i == 0:
			breakpoints.add_breakpoint(file, line)
		if i == 1:
			breakpoints.add_function_breakpoint(args['text'])
		core.run(cancel_select_async)
	def on_cancel():
		core.run(cancel_select_async)
	ui.run_input_command(input, run_main, on_cancel=on_cancel)

