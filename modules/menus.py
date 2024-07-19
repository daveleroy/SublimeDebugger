from __future__ import annotations
from typing import TYPE_CHECKING, Any, Awaitable

if TYPE_CHECKING:
	from .debugger import Debugger

from functools import partial


import sublime
import os

import json
import webbrowser

from .import ui
from .import core
from .import dap

from .settings import Settings
from ..import examples


@core.run
async def example_projects():
	def item(project: str):
		name = os.path.basename(project)
		file = core.package_path(project)

		types = set()

		with open(file) as f:
			data = sublime.decode_value(f.read())
			for configuration in data['debugger_configurations']:
				types.add(configuration['type'])

		types = ', '.join(types)
		return ui.InputListItem(lambda: sublime.active_window().run_command('open_project_or_workspace', { 'file': file }), f'{name} \t{types}')

	await ui.InputList('Example Projects') [
		list(map(item, examples.projects))
	]


@core.run
async def add_configuration(debugger: Debugger):
	debugger.project.open_project_configurations_file()

	return await ui.InputList('Add Debug Configuration')[
		snippets_list_items(debugger)
	]


def format_snippet(snippet: dict[str, Any]):
	body = snippet.get('body', {})


	for (key, value) in body.items():
		# ^ seems to say the value is a json string already
		# https://github.com/microsoft/vscode-json-languageservice/blob/386ce45491130c49e5e59e79ef209cd5de7a2057/src/services/jsonCompletion.ts#L788
		if isinstance(value, str) and value.startswith('^'):
			body[key] = value[2:-1]

	content = json.dumps(body, indent="\t")
	content = content.replace('\\\\', '\\') # remove json encoded \ ...
	content = content.replace('${workspaceFolder}', '${folder}')
	content = content.replace('${workspaceRoot}', '${folder}')
	return content


def snippets_list_items(debugger: Debugger):
	installed: list[ui.InputListItem] = []
	not_installed: list[ui.InputListItem] = []

	for adapter in dap.AdapterConfiguration.registered:
		if not Settings.development and adapter.development:
			continue

		def snippet_item(snippet: Any):
			content = format_snippet(snippet)

			request = snippet.get('body', {}).get('request', '??')
			snippet_item = ui.InputListItem (
				lambda: debugger.project.insert_snippet(content),
				snippet.get('label', 'label'),
				details=request,
				preview=lambda: sublime.Html(f'<code>{ui.html_escape_multi_line(content)}</code>')
			)
			return snippet_item

		def adapter_list_item_installed(adapter: dap.AdapterConfiguration):
			name = adapter.name

			snippet_input_items = list(map(snippet_item, adapter.configuration_snippets))
			subtitle = f'{len(snippet_input_items)} Snippets' if len(snippet_input_items) != 1 else '1 Snippet'

			return ui.InputListItemChecked(
				ui.InputList('Choose a snippet to insert')[
					snippet_input_items
				],
				True,
				name + '\t' + subtitle,
				details= f'<tt>See adapter <a href="{adapter.docs}">documentation</a></tt>'
			)


		def adapter_list_item_not_installed(adapter: dap.AdapterConfiguration) -> ui.InputListItem:
			name = adapter.name
			return ui.InputListItemChecked(
				lambda: dap.AdapterConfiguration.install_adapter(debugger.console, adapter, None),
				False,
				name,
				details=f'<tt>See adapter <a href="{adapter.docs}">documentation</a></tt>'
			)


		if adapter.installed_version:
			installed.append(adapter_list_item_installed(adapter))
		else:
			not_installed.append(adapter_list_item_not_installed(adapter))

	return installed + not_installed



async def change_configuration_input_items(debugger: Debugger) -> list[ui.InputListItem]:
	values: list[ui.InputListItem] = []
	for c in debugger.project.compounds:
		name = f'{c.name}\tcompound'
		values.append(ui.InputListItemChecked(partial(debugger.set_configuration, c), c == debugger.project.configuration_or_compound, name))

	for c in debugger.project.configurations:
		name = f'{c.name}\t{c.type}'
		values.append(ui.InputListItemChecked(partial(debugger.set_configuration, c), c == debugger.project.configuration_or_compound, name))

	if values:
		values.append(ui.InputListItem(lambda: ..., ""))

	values.append(ui.InputListItem(lambda: add_configuration(debugger), 'Add Configuration'))
	values.append(ui.InputListItem(lambda: debugger.project.open_project_configurations_file(), 'Edit Configuration File'))
	values.append(ui.InputListItem(lambda: install_adapters(debugger), 'Install Adapters'))
	return values


@core.run
async def on_settings(debugger: Debugger) -> None:
	def about():
		webbrowser.open_new_tab('https://github.com/daveleroy/sublime_debugger#getting-started')

	def report_issue():
		webbrowser.open_new_tab('https://github.com/daveleroy/sublime_debugger/issues')

	values = await change_configuration_input_items(debugger)

	values.extend([
		ui.InputListItem(lambda: ..., ''),
		ui.InputListItem(report_issue, 'Report Issue', kind=(sublime.KIND_ID_AMBIGUOUS, '⧉', '')),
		ui.InputListItem(about, 'About/Getting Started', kind=(sublime.KIND_ID_AMBIGUOUS, '⧉', '')),
	])

	await ui.InputList('Add or Select Configuration')[
		values
	]


@core.run
async def change_configuration(debugger: Debugger):
	await ui.InputList('Add or Select Configuration')[
		await change_configuration_input_items(debugger)
	]


@core.run
async def install_adapters(debugger: Debugger):
	debugger.console.open()
	items = await install_adapters_list_items(debugger)
	await ui.InputList('Install Adapters - Command/Alt key to list versions')[
		items
	]


async def install_adapters_list_items(debugger: Debugger):
	debugger.console.log('group-start', f'{core.platform.unicode_unchecked_sigil} Fetching Adapters')

	installed: list[Awaitable[ui.InputListItem]] = []
	not_installed: list[Awaitable[ui.InputListItem]] = []
	found_update = False

	for adapter in dap.AdapterConfiguration.registered:
		if not Settings.development and adapter.development:
			continue

		if not adapter.types:
			continue

		async def item(adapter: dap.AdapterConfiguration) -> ui.InputListItem:
			nonlocal found_update

			installed_version = adapter.installed_version or ''
			is_installed = bool(installed_version)

			name = adapter.name if not adapter.development else f'{adapter.name} (dev)'

			def input_list():
				items = [
					ui.InputListItem(partial(dap.AdapterConfiguration.install_adapter, debugger.console, adapter, version), version)
					for version in versions
				]
				if installed_version:
					items.append(ui.InputListItem(lambda: adapter.installer.remove(), 'Remove'))

				return ui.InputList('Choose version to install')[
					items
				]

			def error_item(error: str):
				return ui.InputListItemChecked(
					lambda: ...,
					is_installed,
					f'{name}\t{installed_version}',
					details=f'<tt>{ui.html_escape(error)}</tt>'
				)

			try:
				version, versions = await adapter.installer.installable_versions_with_default(debugger.console)
			except Exception as e:
				debugger.console.error(f'{name}: {e}')
				return error_item(f'Unable to fetch installable versions')


			if installed_version:
				if version != installed_version:
					name += f'\tUpdate Available {installed_version} → {version}'
					debugger.console.log('warn', f'{adapter.name}: Update Available {installed_version} → {version}')
					found_update = True

				else:
					name += f'\t{installed_version}'
			else:
				name += f'\t{version}'

			return ui.InputListItemChecked(
				lambda: dap.AdapterConfiguration.install_adapter(debugger.console, adapter, version),
				is_installed,
				name,
				run_alt=input_list(),
				details=f'<tt>See adapter <a href="{adapter.docs}">documentation</a></tt>'
			)

		if adapter.installed_version:
			installed.append(item(adapter))
		else:
			not_installed.append(item(adapter))

	items = list(await core.gather(*(installed + not_installed)))

	if not found_update:
		debugger.console.log('success', 'All installed Adapters up to date')

	debugger.console.log('group-end', f'{core.platform.unicode_checked_sigil} Finished')
	return items
