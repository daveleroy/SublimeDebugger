from __future__ import annotations
from .typecheck import *

from .debugger import Debugger
from .command import Command, DebuggerExecCommand, CommandDebugger, CommandsRegistry, open_settings

class Commands:
	open = CommandDebugger (
		name='Open',
		action=lambda debugger: debugger.interface.open(),
	)
	quit = CommandDebugger (
		name='Quit',
		action=lambda debugger: debugger.dispose(),
		flags=Command.menu_commands|Command.menu_main|Command.visible_debugger_open,
	)
	settings = Command(
		name='Settings',
		action=open_settings,
		flags=Command.menu_main
	)
	settings = Command(
		name='Preferences: Debugger Settings',
		action=open_settings,
		flags=Command.menu_commands | Command.menu_no_prefix
	)
	generate_commands = Command(
		name='Generate Commands',
		action=lambda _: CommandsRegistry.generate_commands_and_menus(),
		flags=Command.menu_commands
	)
	

	install_adapters = CommandDebugger (
		name='Install Adapters',
		action=lambda debugger: debugger.interface.install_adapters()
	)
	change_configuration = CommandDebugger (
		name='Add or Select Configuration',
		action=lambda debugger: debugger.interface.change_configuration()
	)
	
	add_configuration = CommandDebugger (
		name='Add Configuration',
		action=lambda debugger: debugger.interface.add_configuration()
	)
	
	# - 

	start = CommandDebugger (
		name='Start',
		action=lambda debugger: debugger.interface.start(),
		flags=Command.menu_commands|Command.menu_main|Command.open_without_running|Command.section_start
	)
	start_no_debug = CommandDebugger (
		name='Start (no debug)',
		action=lambda debugger: debugger.interface.start(no_debug=True),
	)
	stop = CommandDebugger (
		name='Stop',
		action=lambda debugger: debugger.interface.stop(),
		enabled=Debugger.is_stoppable
	)

	continue_ = CommandDebugger (
		name='Continue',
		action=lambda debugger: debugger.interface.resume(),
		enabled=Debugger.is_paused
	)
	pause = CommandDebugger (
		name='Pause',
		action=lambda debugger: debugger.interface.pause(),
		enabled=Debugger.is_running,
	)
	step_over = CommandDebugger (
		name='Step Over',
		action=lambda debugger: debugger.interface.step_over(),
		enabled=Debugger.is_paused
	)
	step_in = CommandDebugger (
		name='Step In',
		action=lambda debugger: debugger.interface.step_in(),
		enabled=Debugger.is_paused
	)
	step_out = CommandDebugger (
		name='Step Out',
		action=lambda debugger: debugger.interface.step_out(),
		enabled=Debugger.is_paused
	)

	# -

	input_command = CommandDebugger (
		name='Input Command',
		action=lambda debugger: debugger.interface.on_input_command(),
		flags=Command.section_start
		# enabled=Debugger.is_active
	)
	run_task = CommandDebugger (
		name='Run Task',
		action=Debugger.on_run_task,
	)
	run_last_task = CommandDebugger (
		name='Run Last Task',
		action=Debugger.on_run_last_task,
		flags=Command.menu_main,
	)
	add_function_breakpoint = CommandDebugger (
		name='Add Function Breakpoint',
		action=lambda debugger: debugger.interface.add_function_breakpoint(),
	)
	clear_breakpoints = CommandDebugger (
		name='Clear Breakpoints',
		action=Debugger.clear_all_breakpoints,
		flags=Command.menu_widget|Command.menu_commands|Command.menu_main,
	)
	clear_console = CommandDebugger (
		name='Clear Console',
		action=lambda debugger: debugger.interface.console.clear(),
		flags=Command.menu_widget|Command.menu_commands|Command.menu_main,
	)
	show_protocol = CommandDebugger (
		name='Show Protocol',
		action=Debugger.show_protocol_panel,
		flags=Command.menu_widget|Command.menu_commands|Command.menu_main,
	)
	add_watch_expression = CommandDebugger (
		name='Add Watch Expression',
		action=lambda debugger: debugger.interface.add_watch_expression(),
	)
	save_data = CommandDebugger (
		name='Force Save',
		action=Debugger.save_data,
	)

	# - 

	toggle_breakpoint = CommandDebugger (
		name='Toggle Breakpoint',
		action=lambda debugger: debugger.interface.toggle_breakpoint(),
		flags=Command.menu_context | Command.section_start,
	)
	toggle_column_breakpoint = CommandDebugger (
		name='Toggle Column Breakpoint',
		action=lambda debugger: debugger.interface.toggle_column_breakpoint(),
		flags=Command.menu_context,
	)
	run_to_current_line = CommandDebugger (
		name='Run To Selected Line',
		action=Debugger.run_to_current_line,
		enabled=Debugger.is_paused,
		flags=Command.menu_context,
	)
