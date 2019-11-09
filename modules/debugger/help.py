from .. typecheck import *
from .. import ui

if TYPE_CHECKING:
	from .debugger_interface import DebuggerInterface

import webbrowser

def help_menu(debugger: 'DebuggerInterface') -> ui.InputList:
	def about():
		webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/blob/master/docs/setup.md")
	
	def report_issue():
		webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/issues")


	return ui.InputList ([
		ui.InputListItem(about, "Adapter Documentation"),
		ui.InputListItem(lambda: ..., "---------------------"),
		ui.InputListItem(report_issue, "Report Issue"),
		ui.InputListItem(about, "About/Getting Started"),
	])