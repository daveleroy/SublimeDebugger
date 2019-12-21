from .. typecheck import *
from .. import ui

if TYPE_CHECKING:
	from .debugger import Debugger

import webbrowser

from .adapter import (
	install_adapters_menu,
	select_configuration,
)

def help_menu(debugger: 'Debugger') -> ui.InputList:
	def about():
		webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/blob/master/docs/setup.md")
	
	def report_issue():
		webbrowser.open_new_tab("https://github.com/daveleroy/sublime_debugger/issues")

	values = select_configuration(debugger).values
	values.extend([
		ui.InputListItem(lambda: ..., ""),
		ui.InputListItem(report_issue, "Report Issue"),
		ui.InputListItem(about, "About/Getting Started"),
	])

	return ui.InputList(values)
