from __future__ import annotations
from typing import TYPE_CHECKING
import webbrowser
import sublime


from .settings import SettingsRegistery
from .commands.commands import ExampleProjects

from . import core
from . import ui

if TYPE_CHECKING:
	from .debugger import Debugger


class Suggestions(core.Dispose):
	def __init__(self, debugger: Debugger) -> None:
		self.debugger = debugger
		self.dispose_add(debugger.on_project_or_settings_updated.add(self.refresh))

	def refresh(self):
		console = self.debugger.console
		console.clear()

		if not console.window.project_file_name():
			console.error(f'{core.platform.unicode_checked_sigil} Beware using Debugger outside of a Sublime project has limited functionality')

			console.log(
				'warn',
				'\t- Would you like to create a Sublime Project? ',
				html=ui.Html('<a href="">[Save As Project]</a>', lambda _: (console.window.run_command('save_project_and_workspace_as'), console.debugger.project_or_settings_updated())),
			)
			console.log(
				'warn',
				'\t- Or open an existing project? ',
				html=ui.Html('<a href="">[Open Project]</a>', lambda _: console.window.run_command('prompt_open_project_or_workspace')),
			)
			console.info('\n')

		examples_suggested = True  # console.debugger.project.configurations.count == 0

		console.log('group-start', f'{core.platform.unicode_checked_sigil} Getting Started')

		lsp_json_suggested = not SettingsRegistery.is_package_installed('LSP-json')
		terminus_suggested = not SettingsRegistery.is_package_installed('Terminus')
		autoprojects_suggested = not SettingsRegistery.is_package_installed('AutoProjects')

		if examples_suggested:
			console.log(
				'success',
				'- See `Debugger: Show Examples` to see various example projects ',
				html=ui.Html('<a href="">[Show Examples]</a>', lambda _: console.debugger.run_action(ExampleProjects)),
			)

			console.log(
				'success',
				'- Read the setup instructions for the Debugger package ',
				html=ui.Html('<a href="">[GitHub]</a>', lambda _: webbrowser.open('https://github.com/daveleroy/SublimeDebugger#setup')),
			)

		console.log('group-end', '\n')

		if lsp_json_suggested or terminus_suggested or autoprojects_suggested:
			console.log('group-start', f'{core.platform.unicode_checked_sigil} Suggested Packages')

			if autoprojects_suggested:
				console.log('success', '- Install `AutoProjects` to automatically handle creating Sublime projects ', html=_install_html(['AutoProjects']))

			if lsp_json_suggested:
				console.log('success', '- Install `LSP-json` to provide validation and autocompletion of debug configurations ', html=_install_html(['LSP', 'LSP-json']))

			if terminus_suggested:
				console.log('success', '- Install `Terminus` which is required for debugger tasks and launching your target in a terminal ', html=_install_html(['Terminus']))

			console.log('group-end', '\n')


def _install_html(packages: list[str]):
	return ui.Html('<a href="">[Install]</a>', lambda _: sublime.run_command('install_packages', {'packages': packages}))
