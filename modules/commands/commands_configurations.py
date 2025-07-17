from __future__ import annotations
import os
from typing import TYPE_CHECKING, Any, Awaitable

from functools import partial
import sublime

import json
import webbrowser

from .. import ui
from .. import core
from .. import dap

from ..settings import Settings
from ..command import Action

if TYPE_CHECKING:
	from ..debugger import Debugger


class ExampleProjects(Action):
	name = 'Example Projects'
	key = 'example_projects'

	example_projects = [
		'examples/sublime_debug/sublime.sublime-project',
		'examples/cpp/cpp.sublime-project',
		'examples/csharp/csharp.sublime-project',
		'examples/go/go.sublime-project',
		'examples/csharp/csharp.sublime-project',
		'examples/php/php.sublime-project',
		'examples/python/python.sublime-project',
		'examples/ruby/ruby.sublime-project',
		'examples/web/web.sublime-project',
		'examples/elixir/elixir.sublime-project',
		'examples/lua/lua.sublime-project',
		'examples/java/java.sublime-project',
		'examples/emulicious_debugger/emulicious-debugger.sublime-project',
	]

	def action_raw(self, view: sublime.View | sublime.Window, kwargs: dict[str, Any]):
		def item(project: str):
			name = os.path.basename(project)
			file = core.package_path(project)

			types = set()

			with open(file) as f:
				data = sublime.decode_value(f.read())
				for configuration in data['debugger_configurations']:
					types.add(configuration['type'])

			types = ', '.join(types)

			def open_project():
				sublime.active_window().run_command(
					'open_project_or_workspace',
					{'file': file},
				)
				sublime.active_window().open_file(file)

			return ui.InputListItem(open_project, f'{name} \t{types}')

		core.run(ui.InputList('Example Projects')[list(map(item, self.example_projects))])


class ChangeConfiguration(Action):
	name = 'Add or Select Configuration'
	key = 'change_configuration'

	@core.run
	async def action(self, debugger: Debugger):
		def about():
			webbrowser.open_new_tab('https://github.com/daveleroy/sublime_debugger#getting-started')

		def report_issue():
			webbrowser.open_new_tab('https://github.com/daveleroy/sublime_debugger/issues')


		values: list[ui.InputListItem] = [
			ui.InputListItem(lambda: debugger.run_action(EditConfiguration), EditConfiguration.name + f'\t{debugger.project.project_file_name}'),
			ui.InputListItem(lambda: debugger.run_action(AddConfiguration), AddConfiguration.name),
			ui.InputListItem(lambda: debugger.run_action(InstallAdapters), InstallAdapters.name),
			ui.InputListItem(lambda: ..., ''),
		]

		for c in debugger.project.compounds:
			name = f'{c.name}\tcompound'
			values.append(ui.InputListItemChecked(partial(debugger.set_configuration, c), c == debugger.project.configuration_or_compound, name, run_alt=lambda c=c: c.source and c.source.open_file()))

		for c in debugger.project.configurations:
			name = f'{c.name}\t{c.type}'
			values.append(ui.InputListItemChecked(partial(debugger.set_configuration, c), c == debugger.project.configuration_or_compound, name, run_alt=lambda c=c: c.source and c.source.open_file()))

		values.extend(
			[
				ui.InputListItem(lambda: ..., ''),
				ui.InputListItem(report_issue, 'Report Issue', kind=(sublime.KIND_ID_AMBIGUOUS, '⧉', '')),
				ui.InputListItem(about, 'About/Getting Started', kind=(sublime.KIND_ID_AMBIGUOUS, '⧉', '')),
			]
		)

		await ui.InputList('Add or Select Configuration')[values]


class AddConfiguration(Action):
	name = 'Add Configuration'
	key = 'add_configuration'

	@core.run
	async def action(self, debugger: Debugger):
		debugger.console.open()
		debugger.project.open_project_configurations_file()

		installed: list[ui.InputListItem] = []
		not_installed: list[ui.InputListItem] = []

		for adapter in dap.Adapter.registered:
			if not Settings.development and adapter.development:
				continue

			def snippet_item(snippet: Any):
				content = self._format_snippet(snippet)

				request = snippet.get('body', {}).get('request', '??')
				snippet_item = ui.InputListItem(
					lambda: debugger.project.insert_snippet(content),
					snippet.get('label', 'label'),
					details=request,
					preview=lambda: sublime.Html(f'<code>{ui.html_escape_multi_line(content)}</code>'),
				)
				return snippet_item

			def adapter_list_item_installed(adapter: dap.Adapter):
				name = adapter.name

				snippet_input_items = list(map(snippet_item, adapter.configuration_snippets))
				subtitle = f'{len(snippet_input_items)} Snippets' if len(snippet_input_items) != 1 else '1 Snippet'

				return ui.InputListItemChecked(
					ui.InputList('Choose a snippet to insert')[snippet_input_items],
					True,
					name + '\t' + subtitle,
					details=f'<tt>See adapter <a href="{adapter.docs}">documentation</a></tt>',
				)

			def adapter_list_item_not_installed(adapter: dap.Adapter) -> ui.InputListItem:
				name = adapter.name
				return ui.InputListItemChecked(
					lambda: dap.Adapter.install_adapter(debugger.console, adapter, None),
					False,
					name,
					details=f'<tt>See adapter <a href="{adapter.docs}">documentation</a></tt>',
				)

			if adapter.installed_version:
				installed.append(adapter_list_item_installed(adapter))
			else:
				not_installed.append(adapter_list_item_not_installed(adapter))

		await ui.InputList('Add Debug Configuration')[installed + not_installed]

	def _format_snippet(self, snippet: dict[str, Any]):
		body = snippet.get('body', {})

		for key, value in body.items():
			# ^ seems to say the value is a json string already with the quotes included
			# https://github.com/microsoft/vscode-json-languageservice/blob/386ce45491130c49e5e59e79ef209cd5de7a2057/src/services/jsonCompletion.ts#L788
			if isinstance(value, str) and value.startswith('^'):
				body[key] = value[2:-1]

		content = json.dumps(body, indent='\t')
		content = content.replace('\\\\', '\\')  # remove json encoded \ ...
		content = content.replace('${workspaceFolder}', '${folder}')
		content = content.replace('${workspaceRoot}', '${folder}')
		return content


class EditConfiguration(Action):
	name = 'Edit Configuration File'
	key = 'edit_configurations'

	def action(self, debugger: Debugger):
		debugger.project.open_project_configurations_file()


class InstallAdapters(Action):
	name = 'Install Adapters'
	key = 'install_adapters'

	@core.run
	async def action(self, debugger: Debugger):
		debugger.console.open()
		items = await self.install_adapters_list_items(debugger)
		await ui.InputList('Install Adapters - Command/Alt key to list versions')[items]

	async def install_adapters_list_items(self, debugger: Debugger):
		debugger.console.log('group-start', f'{core.platform.unicode_unchecked_sigil} Fetching Adapters')

		installed: list[Awaitable[ui.InputListItem]] = []
		not_installed: list[Awaitable[ui.InputListItem]] = []
		found_update = False

		for adapter in dap.Adapter.registered:
			if not Settings.development and adapter.development:
				continue

			if not adapter.types:
				continue

			async def item(adapter: dap.Adapter) -> ui.InputListItem:
				nonlocal found_update

				installed_version = adapter.installed_version or ''
				is_installed = bool(installed_version)

				name = adapter.name if not adapter.development else f'{adapter.name} (dev)'

				def input_list():
					items = [ui.InputListItem(partial(dap.Adapter.install_adapter, debugger.console, adapter, version), version) for version in versions]
					if installed_version:
						items.append(ui.InputListItem(lambda: adapter.installer.remove(), 'Remove'))

					return ui.InputList('Choose version to install')[items]

				def error_item(error: str):
					return ui.InputListItemChecked(lambda: ..., is_installed, f'{name}\t{installed_version}', details=f'<tt>{ui.html_escape(error)}</tt>')

				try:
					version, versions = await adapter.installer.installable_versions_with_default(debugger.console)
				except Exception as e:
					debugger.console.error(f'{name}: {e}')
					return error_item('Unable to fetch installable versions')

				if installed_version:
					if version != installed_version:
						name += f'\tUpdate Available {installed_version} → {version}'
						debugger.console.log('warn', f'{adapter.name}: Update Available {installed_version} → {version}')
						found_update = True

					else:
						name += f'\t{installed_version}'
				else:
					name += f'\t{version}'

				return ui.InputListItemChecked(lambda: dap.Adapter.install_adapter(debugger.console, adapter, version), is_installed, name, run_alt=input_list(), details=f'<tt>See adapter <a href="{adapter.docs}">documentation</a></tt>')

			if adapter.installed_version:
				installed.append(item(adapter))
			else:
				not_installed.append(item(adapter))

		items = list(await core.gather(*(installed + not_installed)))

		if not found_update:
			debugger.console.log('success', 'All installed Adapters up to date')

		debugger.console.log('group-end', f'{core.platform.unicode_checked_sigil} Finished')
		return items
