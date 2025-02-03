from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

import sublime

from .views.breakpoints import BreakpointView

from .views.variables import WatchExpressionView

from .views.variable import VariableView

from . import menus
from . import core
from .dap.schema import generate_lsp_json_schema

from .settings import SettingsRegistery

from .debugger import Debugger
from .command import Action, ActionElement, Section, DebuggerCommand

# if you add any commands use this command to regenerate any .sublime-menu files
# this command also regenerates the LSP-json package.json file for any installed adapters



class GenerateContributions(Action):
	name = 'Generate Commands/Settings/Schema'
	key = 'generate_commands'
	development = True

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		DebuggerCommand.generate_commands_and_menus()
		SettingsRegistery.generate_settings()
		generate_lsp_json_schema()


class Open(Action):
	name = 'Open'
	key = 'open'

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		print("OPEN")
		Debugger.create(view).open()

class Quit(Action):
	name = 'Quit'
	key = 'quit'

	def action(self, debugger: Debugger):
		debugger.dispose()


# class Settings(Action):
# 	name = 'Settings'
# 	key = 'settings'

# 	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
# 		if window := core.window_from_view_or_widow(view):
# 			window.run_command('edit_settings', {'base_file': '${packages}/Debugger/Debugger.sublime-settings'})

class SettingsPreferences(Action):
	name = 'Preferences: Debugger Settings'
	key = 'settings_preferences'
	is_menu_main = False
	prefix_menu_name = False

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		if window := core.window_from_view_or_widow(view):
			window.run_command('edit_settings', {'base_file': '${packages}/Debugger/Debugger.sublime-settings'})


class BrowseStorage(Action):
	name = 'Browse Package storage'
	key = 'browse_storage'

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		if window := core.window_from_view_or_widow(view):
			window.run_command('open_dir', {'dir': core.debugger_storage_path(ensure_exists=True)})


class InstallAdapters(Action):
	name = 'Install Adapters'
	key = 'install_adapters'

	def action(self, debugger: Debugger):
		menus.install_adapters(debugger)


class ChangeConfiguration(Action):
	name = 'Add or Select Configuration'
	key = 'change_configuration'

	def action(self, debugger: Debugger):
		menus.change_configuration(debugger)


class AddConfiguration(Action):
	name = 'Add Configuration'
	key = 'add_configuration'

	def action(self, debugger: Debugger):
		menus.add_configuration(debugger)


class EditConfiguration(Action):
	name = 'Edit Configurations'
	key = 'edit_configurations'

	def action(self, debugger: Debugger):
		debugger.project.open_project_configurations_file()


class ExampleProjects(Action):
	name = 'Example Projects'
	key = 'example_projects'

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		menus.example_projects()


Section()


class Start(Action):
	name = 'Start'
	key = 'start'

	# if not on the console tab this command will open the console tab and not run the command
	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		debugger = Debugger.get(view)

		# create the debugger but do not start the command
		if not debugger:
			Debugger.create(view)
			return

		# if the console isn't open open the console and dont run the command
		if not debugger.console.is_open():
			debugger.console.open()
			return

		debugger.start(args=kwargs)

class OpenAndStart(Action):
	name = ''
	key = 'open_and_start'

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		debugger = Debugger.create(view, skip_project_check=True)
		debugger.start(args=kwargs)


class StartNoDebug(Action):
	name = 'Start (no debug)'
	key = 'start_no_debug'

	def action(self, debugger: Debugger):
		debugger.start(no_debug=True)


class Stop(Action):
	name = 'Stop'
	key = 'stop'

	def action(self, debugger: Debugger):
		debugger.stop()

	def is_enabled(self, debugger: Debugger):
		return debugger.is_stoppable()


class Continue(Action):
	name = 'Continue'
	key = 'continue'

	def action(self, debugger: Debugger):
		debugger.resume()

	def is_enabled(self, debugger: Debugger):
		return debugger.is_paused()


class Pause(Action):
	name = 'Pause'
	key = 'pause'

	def action(self, debugger: Debugger):
		debugger.pause()

	def is_enabled(self, debugger: Debugger):
		return debugger.is_running()


class StepOver(Action):
	name = 'Step Over'
	key = 'step_over'

	def action(self, debugger: Debugger):
		debugger.step_over()

	def is_enabled(self, debugger: Debugger):
		return debugger.is_paused()


class StepIn(Action):
	name = 'Step In'
	key = 'step_in'

	def action(self, debugger: Debugger):
		debugger.step_in()

	def is_enabled(self, debugger: Debugger):
		return debugger.is_paused()


class StepOut(Action):
	name = 'Step Out'
	key = 'step_out'

	def action(self, debugger: Debugger):
		debugger.step_out()

	def is_enabled(self, debugger: Debugger):
		return debugger.is_paused()


Section()

class ReverseContinue(Action):
	name = 'Reverse Continue'
	key = 'reverse_continue'

	def action(self, debugger: Debugger):
		debugger.reverse_continue()

	def is_enabled(self, debugger: Debugger):
		return debugger.is_paused_and_reversable()


class StepBack(Action):
	name = 'Step Back'
	key = 'step_back'

	def action(self, debugger: Debugger):
		debugger.step_back()

	def is_enabled(self, debugger: Debugger):
		return debugger.is_paused_and_reversable()


Section()

class InputCommand(Action):
	name = 'Input Command'
	key = 'input_command'

	def action(self, debugger: Debugger):
		debugger.on_input_command()


class RunTask(Action):
	name = 'Run Task'
	key = 'run_task'

	def action(self, debugger: Debugger):
		debugger.on_run_task()


class RunLastTask(Action):
	name = 'Select & Run Task'
	key = 'select_and_run_task'

	def action(self, debugger: Debugger):
		debugger.on_run_task(select=True)


class AddFunctionBreakpoint(Action):
	name = 'Add Function Breakpoint'
	key = 'add_function_breakpoint'

	def action(self, debugger: Debugger):
		debugger.add_function_breakpoint()


class AddWatchExpression(Action):
	name = 'Add Watch Expression'
	key = 'add_watch_expression'

	def action(self, debugger: Debugger):
		debugger.add_watch_expression()


class ForceSave(Action):
	name = 'Force Save'
	key = 'save_data'

	def action(self, debugger: Debugger):
		debugger.save_data()


Section()


class ToggleBreakpoint(Action):
	name = 'Toggle Breakpoint'
	key = 'toggle_breakpoint'
	is_menu_context = True

	def action(self, debugger: Debugger):
		debugger.toggle_breakpoint()


class ToggleColumnBreakpoint(Action):
	name = 'Toggle Column Breakpoint'
	key = 'toggle_column_breakpoint'
	is_menu_context = True

	def action(self, debugger: Debugger):
		debugger.toggle_column_breakpoint()


class RunToSelectedLine(Action):
	name = 'Run To Selected Line'
	key = 'run_to_current_line'
	is_menu_context = True

	def action(self, debugger: Debugger):
		debugger.run_to_current_line()

	def is_enabled(self, debugger: Debugger) -> bool:
		return debugger.is_paused()


class ToggleDisassembly(Action):
	name = 'Toggle Disassembly'
	key = 'toggle_disassembly'
	is_menu_context = True

	def action(self, debugger: Debugger):
		debugger.show_disassembly(toggle=True)

Section()

class ShowProtocol(Action):
	name = 'Show Protocol'
	key = 'show_protocol'

	def action(self, debugger: Debugger):
		debugger.console.protocol.open()


class VariableCopyValue(ActionElement):
	name = 'Copy Value'
	key = 'variable_copy_value'
	view = VariableView

	def action(self, debugger: Debugger, element: VariableView):
		element.copy_value()


class VariableCopyAsExpression(ActionElement):
	name = 'Copy as Expression'
	key = 'variable_copy_expression'
	element = VariableView

	def action(self, debugger: Debugger, element: VariableView):
		element.copy_expr()


class VariableAddToWatch(ActionElement):
	name = 'Add To Watch'
	key = 'variable_add_to_watch'
	element = VariableView

	def action(self, debugger: Debugger, element: VariableView):
		element.add_watch()


class WatchRemoveExpression(ActionElement):
	name = 'Remove Expression'
	key = 'watch_remove_expression'
	element = WatchExpressionView

	def action(self, debugger: Debugger, element: WatchExpressionView):
		debugger.watch.remove(element.expression)


class WatchRemoveAllExpression(ActionElement):
	name = 'Remove All Expressions'
	key = 'watch_remove_all_expressions'
	element = WatchExpressionView

	def action(self, debugger: Debugger, element: WatchExpressionView):
		debugger.watch.remove_all()


class EditBreakpoint(ActionElement):
	name = 'Edit Breakpoint'
	key = 'edit_breakpoint'
	element = BreakpointView

	def action(self, debugger: Debugger, element: BreakpointView):
		element.edit()


class RemoveBreakpoint(ActionElement):
	name = 'Remove Breakpoint'
	key = 'remove_breakpoint'
	element = BreakpointView

	def action(self, debugger: Debugger, element: BreakpointView):
		element.remove()

	def is_visible(self, debugger: Debugger, element: BreakpointView):
		return element.is_removeable()


class RemoveAllBreakpoints(ActionElement):
	name = 'Remove All Breakpoints'
	key = 'remove_all_breakpoints'
	element = BreakpointView

	def action(self, debugger: Debugger, element: BreakpointView):
		debugger.breakpoints.remove_all()

	def is_visible(self, debugger: Debugger, element: BreakpointView):
		return element.is_removeable()

