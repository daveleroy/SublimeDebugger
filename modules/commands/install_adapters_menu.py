import sublime
import sublime_plugin

from .. import core
from .. import ui

from ..debugger.adapter_configuration import AdapterConfiguration, install_adapter
from ..debugger.debugger_interface import DebuggerInterface


def open_install_adapter_menu(debugger: DebuggerInterface, selected_index = 0):
	values = []
	adapters = []
	for adapter in debugger.adapters.values():
		if not adapter.installation:
			continue
		adapters.append(adapter)
		if adapter.installing:
			values.append(ui.ListInputItem("◐ {}".format(adapter.installation.name)))
		elif adapter.installed:
			values.append(ui.ListInputItem("● {}".format(adapter.installation.name)))
		else:
			values.append(ui.ListInputItem("○ {}".format(adapter.installation.name)))
		
	def input (selected_index):
		return ui.ListInput(values, placeholder="install debug adapter clients", index=selected_index)

	@core.async
	def run_async(list, adapter):
		debugger.terminal.log_info("installing debug adapter...")
		try: 
			yield from install_adapter(adapter)
		except Exception as e:
			debugger.terminal.log_error(str(e))
			debugger.terminal.log_error("... debug adapter installed failed")
		finally:
			adapter.installing = False
		debugger.terminal.log_info("... debug adapter installed")
		
		open_install_adapter_menu(debugger, list)

	def run(list):
		print('installing')
		adapter = adapters[list]
		adapter.installing = True
		open_install_adapter_menu(debugger, list)
		core.run(run_async(list, adapter))

	def run_not_main(list):
		ui.run_input_command(input(selected_index), run)

	ui.run_input_command(input(selected_index), run, run_not_main=run_not_main)
