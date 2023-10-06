from __future__ import annotations
from typing import TYPE_CHECKING, Any, Awaitable

if TYPE_CHECKING:
	from .debugger import Debugger
	from .project import Project

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
	for (key, value) in snippet.items():
		if isinstance(value, str) and value.startswith('^"') and value.endswith('"'):
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
			name = adapter.types[0]

			snippet_input_items = list(map(snippet_item, adapter.configuration_snippets))
			subtitle = f'{len(snippet_input_items)} Snippets' if len(snippet_input_items) != 1 else '1 Snippet'

			return ui.InputListItemChecked(
				ui.InputList('Choose a snippet to insert')[
					snippet_input_items
				],
				True,
				name + '\t' + subtitle,
				details= f'<a href="{adapter.docs}">documentation</a>'
			)


		def adapter_list_item_not_installed(adapter: dap.AdapterConfiguration) -> ui.InputListItem:
			name = adapter.types[0]
			return ui.InputListItemChecked(
				lambda: dap.AdapterConfiguration.install_adapter(debugger.console, adapter, None),
				False,
				name,
				details=f'<a href="{adapter.docs}">documentation</a>'
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
	await ui.InputList('Install/Update Debug Adapters')[
		items
	]


async def install_adapters_list_items(debugger: Debugger):
	debugger.console.log('group-start', '[Checking For Updates]')

	installed: list[Awaitable[ui.InputListItem]] = []
	not_installed: list[Awaitable[ui.InputListItem]] = []

	for adapter in dap.AdapterConfiguration.registered:
		if not Settings.development and adapter.development:
			continue

		if not adapter.types:
			continue

		async def item(adapter: dap.AdapterConfiguration) -> ui.InputListItem:
			installed_version = adapter.installed_version
			name = adapter.types[0] if not adapter.development else f'{adapter.types[0]} (dev)'

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
					installed_version != None,
					name,
					details=error
				)

			try:
				versions: list[str] = await adapter.installer.installable_versions(debugger.console)
			except Exception as e:
				return error_item(f'Unable to fetch installable version: {e}')

			none_beta_releases = list(filter(lambda r: not ('pre' in r or 'beta' in r or 'alpha' in r), versions))

			if not versions or not none_beta_releases:
				return error_item(f'No installable versions found')

			if installed_version:
				if versions and none_beta_releases[0] != installed_version:
					name += f'\tUpdate Available {installed_version} → {none_beta_releases[0]}'
					debugger.console.log('warn', f'{adapter.type}: Update Available {installed_version} → {none_beta_releases[0]}')
				else:
					name += f'\t{installed_version}'

			return ui.InputListItemChecked(
				lambda: dap.AdapterConfiguration.install_adapter(debugger.console, adapter, none_beta_releases[0]),
				installed_version != None,
				name,
				run_alt=input_list(),
				details=f'<a href="{adapter.docs}">documentation</a>'
			)

		if adapter.installed_version:
			installed.append(item(adapter))
		else:
			not_installed.append(item(adapter))

	items = list(await core.gather(*(installed + not_installed)))
	debugger.console.log('group-end', '[Finished]')
	return items
