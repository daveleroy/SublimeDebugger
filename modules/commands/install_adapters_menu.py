import sublime
import sublime_plugin

from .. import core
from .. import ui

from ..debugger.adapter_configuration import AdapterConfiguration, install_adapter
from ..debugger.debugger_interface import DebuggerInterface

from .debugger import DebuggerCommand

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
		
		debugger.console_panel.Add("installing debug adapter...")
		try: 
			yield from install_adapter(adapter)
		except Exception as e:
			debugger.console_panel.Add(str(e))
			debugger.console_panel.Add("... debug adapter installed failed")
		finally:
			adapter.installing = False
		debugger.console_panel.Add("... debug adapter installed")
		
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


class DebuggerInstallAdapter(DebuggerCommand):
	def on_main(self, debugger: DebuggerInterface) -> None:
		open_install_adapter_menu(debugger)
