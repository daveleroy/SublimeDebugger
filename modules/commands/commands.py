from __future__ import annotations
from typing import TYPE_CHECKING, Any

import sublime


from .. import dap
from .. import core
from .. import ui

from ..dap.schema import generate_lsp_json_schema
from ..settings import SettingsRegistery
from ..command import Action, Section, DebuggerCommand

if TYPE_CHECKING:
	from ..debugger import Debugger


class SettingsPreferences(Action):
	name = 'Preferences: Debugger Settings'
	key = 'settings_preferences'
	is_menu_main = False
	prefix_menu_name = False

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		if window := core.window_from_view_or_widow(view):
			window.run_command('edit_settings', {'base_file': '${packages}/Debugger/Debugger.sublime-settings'})


class Open(Action):
	name = 'Open'
	key = 'open'

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		from ..debugger import Debugger

		window = core.window_from_view_or_widow(view)
		if not window:
			return

		debugger = Debugger.get(window)
		if debugger:
			debugger.open()
			return

		if not window.project_file_name():
			sublime.error_message('`Debugger: Open` requires a Sublime project')
			return

		if not debugger:
			debugger = Debugger.create(window)


class OpenOutsideProject(Action):
	name = 'Open (Ignore Sublime Project Restriction)'
	key = 'open_outside_project'

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		from ..debugger import Debugger

		debugger = Debugger.create(view)
		debugger.open()

	def _is_visible(self, view: sublime.View | sublime.Window, **kwargs: dict[str, Any]):
		window = core.window_from_view_or_widow(view)
		if not window:
			return False

		return not window.project_file_name()


class Quit(Action):
	name = 'Quit'
	key = 'quit'

	def action(self, debugger: Debugger):
		debugger.dispose()


Section()
from .commands_configurations import InstallAdapters
from .commands_configurations import ChangeConfiguration
from .commands_configurations import AddConfiguration
from .commands_configurations import EditConfiguration
from .commands_configurations import ExampleProjects


Section()
from .commands_session import Start
from .commands_session import StartNoDebug
from .commands_session import Stop
from .commands_session import Continue
from .commands_session import Pause
from .commands_session import StepOver
from .commands_session import StepIn
from .commands_session import StepOut

Section()

from .commands_session import ReverseContinue
from .commands_session import StepBack


Section()


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


class NewTerminal(Action):
	name = 'New Terminal'
	key = 'new_terminal'

	@core.run
	async def action(self, debugger: Debugger):
		debugger.dispose_terminals(unused_only=True)

		for task in debugger.tasks.tasks:
			if task.task.name == 'Terminal':
				await ui.InputText(
					lambda name: self.create(debugger, name),
					'Create New Terminal With Name',
				)
				return

		await self.create(debugger, 'Terminal')

	@core.run
	async def create(self, debugger: Debugger, name: str):
		task = await dap.Task({'name': name}).Expanded({})
		await debugger.tasks.run(debugger, task)


class OpenTerminal(Action):
	name = 'Open Terminal'
	key = 'open_terminal'

	@core.run
	async def action(self, debugger: Debugger):
		if not debugger.tasks.tasks:
			debugger.run_action(NewTerminal)
			return

		next_task = 0

		for i, task in enumerate(debugger.tasks.tasks):
			if task.is_open():
				next_task = i + 1
				break

		next_task = debugger.tasks.tasks[next_task % len(debugger.tasks.tasks)]
		next_task.open()


Section()


class AddFunctionBreakpoint(Action):
	name = 'Add Function Breakpoint'
	key = 'add_function_breakpoint'

	@core.run
	async def action(self, debugger: Debugger):
		def add(name: str):
			if not name:
				return

			debugger.breakpoints.function.add(name)

		await ui.InputText(add, 'Name of function to break on')


class AddWatchExpression(Action):
	name = 'Add Watch Expression'
	key = 'add_watch_expression'

	@core.run
	async def action(self, debugger: Debugger):
		def add(value: str):
			if not value:
				return

			debugger.watch.add(value)

		await ui.InputText(add, 'Expression to watch')


Section()


class ToggleBreakpoint(Action):
	name = 'Toggle Breakpoint'
	key = 'toggle_breakpoint'
	is_menu_context = True

	def action(self, debugger: Debugger):
		file, line, _ = debugger.project.current_file_line_column()
		debugger.breakpoints.source.toggle(file, line)


class ToggleColumnBreakpoint(Action):
	name = 'Toggle Column Breakpoint'
	key = 'toggle_column_breakpoint'
	is_menu_context = True

	def action(self, debugger: Debugger):
		file, line, column = debugger.project.current_file_line_column()
		debugger.breakpoints.source.toggle(file, line, column)


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


class BrowseStorage(Action):
	name = 'Browse Package storage'
	key = 'browse_storage'

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		if window := core.window_from_view_or_widow(view):
			window.run_command('open_dir', {'dir': core.debugger_storage_path(ensure_exists=True)})


class ShowProtocol(Action):
	name = 'Show Protocol'
	key = 'show_protocol'

	def action(self, debugger: Debugger):
		debugger.console.protocol.open()


class ForceSave(Action):
	name = 'Force Save'
	key = 'save_data'

	def action(self, debugger: Debugger):
		debugger.save_data()


Section()

# These are all element commands and only active when using a context menu on a ui element
from .commands_variables import VariableCopyValue
from .commands_variables import VariableCopyAsExpression
from .commands_variables import VariableAddToWatch
from .commands_variables import WatchRemoveExpression
from .commands_variables import WatchRemoveAllExpression

from .commands_breakpoints import EditBreakpoint
from .commands_breakpoints import RemoveBreakpoint
from .commands_breakpoints import RemoveAllBreakpoints


# Internal Commands
class CallstackEnterCommand(Action):
	name = ''
	key = 'callstack_toggle_input'

	def action(self, debugger: Debugger):
		debugger.console.open()
		debugger.console.enter()

	def is_visible(self, debugger: Debugger) -> bool:
		return False


# if you add any commands use this command to regenerate any .sublime-menu files
# this command also regenerates the LSP-json package.json file for any installed adapters
class GenerateContributions(Action):
	name = 'Generate Contributions'
	key = 'generate_contributions'
	development = True

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		DebuggerCommand.generate_commands_and_menus()
		SettingsRegistery.generate_settings()
		generate_lsp_json_schema()
