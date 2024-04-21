from __future__ import annotations

from .import menus
from .import core
from .dap.schema import generate_lsp_json_schema

from .settings import SettingsRegistery

from .debugger import Debugger
from .command import Command, CommandsRegistry

class Commands:

	# if you add any commands use this command to regenerate any .sublime-menu files
	# this command also regenerates the LSP-json package.json file for any installed adapters
	generate_commands = Command(
		name='Generate Commands/Settings/Schema',
		key='generate_commands',
		window_action=lambda window: (CommandsRegistry.generate_commands_and_menus(), generate_lsp_json_schema(), SettingsRegistery.generate_settings()),
		flags=Command.menu_commands|Command.development
	)
	open = Command (
		name='Open',
		key='open',
		action=lambda debugger: debugger.open(),
	)
	quit = Command (
		name='Quit',
		key='quit',
		action=lambda debugger: debugger.dispose(),
		flags=Command.menu_commands|Command.menu_main|Command.visible_debugger_open,
	)
	settings = Command(
		name='Settings',
		key='settings',
		window_action=lambda window: window.run_command('edit_settings', { 'base_file': '${packages}/Debugger/Debugger.sublime-settings' }),
		flags=Command.menu_main
	)
	settings = Command(
		name='Preferences: Debugger Settings',
		key='settings',
		window_action=lambda window: window.run_command('edit_settings', { 'base_file': '${packages}/Debugger/Debugger.sublime-settings' }),
		flags=Command.menu_commands | Command.menu_no_prefix
	)
	browse_storage = Command(
		name='Debugger: Browse Package storage',
		key='browse_storage',
		window_action=lambda window: window.run_command('open_dir', { 'dir': core.debugger_storage_path(ensure_exists=True) }),
		flags=Command.menu_commands | Command.menu_no_prefix
	)
	install_adapters = Command (
		name='Install Adapters',
		key='install_adapters',
		action=lambda debugger: menus.install_adapters(debugger)
	)
	change_configuration = Command (
		name='Add or Select Configuration',
		key='change_configuration',
		action=lambda debugger: menus.change_configuration(debugger)
	)

	add_configuration = Command (
		name='Add Configuration',
		key='add_configuration',
		action=lambda debugger: menus.add_configuration(debugger)
	)

	add_configuration = Command (
		name='Edit Configurations',
		key='edit_configurations',
		action=lambda debugger: debugger.project.open_project_configurations_file()
	)

	example_projects = Command (
		name='Example Projects',
		key='example_projects',
		action=lambda debugger: menus.example_projects()
	)

	Command('-')

	start = Command (
		name='Start',
		key='start',
		action=lambda debugger, **args: debugger.start(False, args),
		flags=Command.menu_commands|Command.menu_main|Command.open_without_running|Command.allow_debugger_outside_project
	)
	open_and_start = Command (
		name='Open and Start',
		key='open_and_start',
		action=lambda debugger, **args: debugger.start(False, args),
		flags=Command.allow_debugger_outside_project
	)
	start_no_debug = Command (
		name='Start (no debug)',
		key='start_no_debug',
		action=lambda debugger: debugger.start(True, None),
	)
	stop = Command (
		name='Stop',
		key='stop',
		action=lambda debugger: debugger.stop(None),
		enabled=Debugger.is_stoppable
	)
	continue_ = Command (
		name='Continue',
		key='continue',
		action=lambda debugger: debugger.resume(),
		enabled=Debugger.is_paused
	)
	pause = Command (
		name='Pause',
		key='pause',
		action=lambda debugger: debugger.pause(),
		enabled=Debugger.is_running,
	)
	step_over = Command (
		name='Step Over',
		key='step_over',
		action=lambda debugger: debugger.step_over(),
		enabled=Debugger.is_paused
	)
	step_in = Command (
		name='Step In',
		key='step_in',
		action=lambda debugger: debugger.step_in(),
		enabled=Debugger.is_paused
	)
	step_out = Command (
		name='Step Out',
		key='step_out',
		action=lambda debugger: debugger.step_out(),
		enabled=Debugger.is_paused
	)

	Command('-')

	reverse_continue = Command (
		name='Reverse Continue',
		key='reverse_continue',
		action=lambda debugger: debugger.reverse_continue(),
		enabled=Debugger.is_paused_and_reversable
	)
	step_back = Command (
		name='Step Back',
		key='step_back',
		action=lambda debugger: debugger.step_back(),
		enabled=Debugger.is_paused_and_reversable
	)

	Command('-')

	input_command = Command (
		name='Input Command',
		key='input_command',
		action=lambda debugger: debugger.on_input_command(),
	)
	run_task = Command (
		name='Run Task',
		key='run_task',
		action=lambda debugger: debugger.on_run_task(),
	)
	run_last_task = Command (
		name='Run Last Task',
		key='run_last_task',
		action=lambda debugger: debugger.on_run_last_task(),
		flags=Command.menu_main,
	)
	add_function_breakpoint = Command (
		name='Add Function Breakpoint',
		key='add_function_breakpoint',
		action=lambda debugger: debugger.add_function_breakpoint(),
	)
	clear_breakpoints = Command (
		name='Clear Breakpoints',
		key='clear_breakpoints',
		action=lambda debugger: debugger.clear_all_breakpoints(),
		flags=Command.menu_widget|Command.menu_commands|Command.menu_main,
	)
	clear_console = Command (
		name='Clear Console',
		key='clear_console',
		action=lambda debugger: debugger.console.clear(),
		flags=Command.menu_widget|Command.menu_commands|Command.menu_main,
	)
	show_protocol = Command (
		name='Show Protocol',
		key='show_protocol',
		action=lambda debugger: debugger.console.protocol.open(),
		flags=Command.menu_widget|Command.menu_commands|Command.menu_main,
	)
	add_watch_expression = Command (
		name='Add Watch Expression',
		key='add_watch_expression',
		action=lambda debugger: debugger.add_watch_expression(),
	)
	save_data = Command (
		name='Force Save',
		key='save_data',
		action=lambda debugger: debugger.save_data(),
	)

	Command('-')

	toggle_disassembly = Command (
		name='Toggle Disassembly',
		key='toggle_disassembly',
		action=lambda debugger: debugger.show_disassembly(toggle=True),
		flags=Command.menu_context|Command.menu_commands
	)
	toggle_breakpoint = Command (
		name='Toggle Breakpoint',
		key='toggle_breakpoint',
		action=lambda debugger: debugger.toggle_breakpoint(),
		flags=Command.menu_context,
	)
	toggle_column_breakpoint = Command (
		name='Toggle Column Breakpoint',
		key='toggle_column_breakpoint',
		action=lambda debugger: debugger.toggle_column_breakpoint(),
		flags=Command.menu_context,
	)
	run_to_current_line = Command (
		name='Run To Selected Line',
		key='run_to_current_line',
		action=lambda debugger: debugger.run_to_current_line(),
		enabled=Debugger.is_paused,
		flags=Command.menu_context,
	)

	Command('-')
