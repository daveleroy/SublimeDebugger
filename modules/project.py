from __future__ import annotations
from pathlib import Path
from typing import Any, cast
from . import core
from . import dap

from .inputs import SelectProcess

from .dap import Configuration, ConfigurationCompound, Task
from .settings import Settings

import sublime
import os

import contextlib


class Project:
	def __init__(self, window: sublime.Window):
		self.window = window
		self.on_updated = core.Event[None]()

		self.tasks: list[Task] = []
		self.compounds: list[ConfigurationCompound] = []
		self.configurations: list[Configuration] = []

		self.configuration_or_compound: Configuration | ConfigurationCompound | None = None

	def dispose(self): ...

	@property
	def location(self) -> str | None:
		if project_name := self.window.project_file_name():
			return project_name
		return None

	@property
	def project_file_name(self) -> str | None:
		if project_name := self.window.project_file_name():
			return Path(project_name).name
		return ''


	@property
	def name(self) -> str:
		if self.configuration_or_compound:
			return self.configuration_or_compound.name

		return 'Add Configuration'

	def into_json(self) -> dict[str, Any]:
		return {
			'configuration_name': self.configuration_or_compound and self.configuration_or_compound.name,
			'configuration_id_ish': self.configuration_or_compound and self.configuration_or_compound.id_ish,
		}

	def load_from_json(self, json: dict[str, Any]) -> Configuration | ConfigurationCompound | None:
		configuration_name: str | None = json.get('configuration_name')
		configuration_id_ish: str | None = json.get('configuration_id_ish')

		if configuration_name and configuration_id_ish:
			self.load_configuration(configuration_name, configuration_id_ish)

	def load_configuration(self, configuration_name: str, configuration_id_ish: str = '', skip_update: bool = False):
		def find_matching_configuration():
			for compound in self.compounds:
				if compound.id_ish == configuration_id_ish:
					return compound
			for configuration in self.configurations:
				if configuration.id_ish == configuration_id_ish:
					return configuration

			for compound in self.compounds:
				if compound.name == configuration_name:
					return compound
			for configuration in self.configurations:
				if configuration.name == configuration_name:
					return configuration
			return None

		previous_configuration_or_compound = self.configuration_or_compound
		self.configuration_or_compound = find_matching_configuration()

		if previous_configuration_or_compound != self.configuration_or_compound:
			if not skip_update:
				self.on_updated()

			return True

		return False

	def get_task(self, name: str) -> Task:
		for task in self.tasks:
			if task.name == name:
				return task
		raise dap.Error(f'Unable to find task with name "{name}"')

	def active_configurations(self) -> list[Configuration]:
		if isinstance(self.configuration_or_compound, ConfigurationCompound):
			configurations: list[Configuration] = []
			for configuration_name in self.configuration_or_compound.configurations:
				configuration = None
				for c in self.configurations:
					if c.name == configuration_name:
						configuration = c
						break

				if configuration:
					configurations.append(configuration)
				else:
					raise dap.Error(f'Unable to find configuration with name "{configuration_name}" while evaluating compound "{self.configuration_or_compound.name}"')

			return configurations

		if isinstance(self.configuration_or_compound, Configuration):
			return [self.configuration_or_compound]

		return []

	@core.run
	async def open_project_configurations_file(self):
		project_name = self.window.project_file_name()
		if not project_name:
			self.window.run_command('edit_settings', {'base_file': '${packages}/Debugger/Debugger.sublime-settings'})
			return None, None

		view = await core.sublime_open_file_async(self.window, project_name)
		region = view.find(r""""\s*debugger_configurations\s*"\s*:\s*\[""", 0)
		if region:
			view.show_at_center(region)

		return view, region

	@core.run
	async def insert_snippet(project: Project, snippet: str):
		try:
			view, region = await project.open_project_configurations_file()
			if not region or not view:
				raise dap.Error('Unable to find debugger_configurations')

			view.sel().clear()
			view.sel().add(sublime.Region(region.b, region.b))
			view.run_command('insert', {'characters': '\n'})
			view.run_command('insert_snippet', {'contents': snippet + ','})

		except dap.Error:
			core.exception()
			sublime.set_clipboard(snippet)
			core.display('Unable to insert configuration into sublime-project file: Copied to clipboard instead')

	def reload(self, console: dap.Console):
		core.info('ProjectConfiguration.reload')
		self._load_configurations(console)
		self.on_updated()

	def _extract_from_project_data(self, project_data: Any, key: str) -> list[tuple[Any, dap.SourceLocation]]:
		configurations: list[tuple[Any, dap.SourceLocation]] = []

		if location := self.location:
			source = dap.SourceLocation.from_path(location, line_regex=key)
			for configuration_or_file in project_data.get(key, []):
				configurations.append((configuration_or_file, source))

		if global_configurations := getattr(Settings, f'global_{key}'):
			source = dap.SourceLocation.from_path('Debugger.sublime-settings', line_regex=key)
			configurations += map(lambda i: (i, source), global_configurations)

		# This is basically only for developing the Debugger package so we can have all the example configurations accessible
		debugger_include_examples = project_data.get('debugger_include_examples') == True
		if debugger_include_examples:
			from .commands.commands_configurations import ExampleProjects

			for example_project in ExampleProjects.example_projects:
				if not os.path.isabs(example_project):
					example_project = os.path.join(self.window.extract_variables()['folder'], example_project)

				with open(example_project, 'r') as file:
					contents = file.read()

				project_json: Any = sublime.decode_value(contents) or {}
				json: list[Any] = project_json.get(key, [])
				for configuration in json:
					configuration['$'] = {'project_path': os.path.dirname(example_project), 'folder': os.path.dirname(example_project)}

				source = dap.SourceLocation.from_path(example_project, line_regex=key)
				configurations.extend(map(lambda i: (i, source), json))

		return configurations

	def project_data(self)-> dict[str, Any]:
		return cast(Any, self.window.project_data())

	def _load_configurations(self, console: dap.Console):
		data = self.project_data()
		if data is None:
			core.info('No project associated with window')
			data = {}

		# add the empty debugger_configurations if needed
		elif not 'debugger_configurations' in data:
			core.info('Adding `debugger_configurations` to sublime-project data')
			data['debugger_configurations'] = []
			self.window.set_project_data(data)

		tasks: list[Task] = []
		configurations: list[Configuration] = []
		compounds: list[ConfigurationCompound] = []

		@contextlib.contextmanager
		def report_issues(name: str, json: Any, source: dap.SourceLocation):
			try:
				yield
			except KeyError as e:
				console.log('warn', f'{source.name}: {name} requires {e} field', source)
				console.info(core.json_encode(json, pretty=True))

		for json, source in self._extract_from_project_data(data, 'debugger_configurations'):
			with report_issues('Configuration', json, source):
				configurations.append(Configuration.from_json(json, len(configurations), source))

		for json, source in self._extract_from_project_data(data, 'debugger_compounds'):
			with report_issues('Configuration Compound', json, source):
				compounds.append(ConfigurationCompound.from_json(json, len(compounds), source))

		for json, source in self._extract_from_project_data(data, 'debugger_tasks'):
			with report_issues('Task', json, source):
				tasks.append(Task.from_json(json, source))

		self.configurations = configurations
		self.compounds = compounds
		self.tasks = tasks

		# reselect the old configuration
		if self.configuration_or_compound:
			self.load_configuration(self.configuration_or_compound.name, self.configuration_or_compound.id_ish, skip_update=True)

	def is_source_file(self, view: sublime.View) -> bool:
		return bool(self.source_file(view))

	def source_file(self, view: sublime.View) -> str | None:
		if view.window() != self.window:
			return None

		if view.settings().get('debugger.view.source') is False:
			return None

		return view.file_name()

	def extract_variables(self):
		variables: dict[str, str] = self.window.extract_variables()

		# patch in some vscode variables
		if folder := variables.get('folder'):
			variables['workspaceFolder'] = folder
			variables['workspaceRoot'] = folder

		variables['packages'] = sublime.packages_path()

		inputs: dict[str, dap.Input] = {
			'select_process': SelectProcess(),
		}

		for key, value in variables.items():
			inputs[key] = dap.InputLiteral(value)

		return inputs

	def current_file_line_column(self) -> tuple[str, int, int]:
		view = self.window.active_view()
		if not view:
			raise dap.Error('No open view')

		file = self.source_file(view)
		if not file:
			raise dap.Error('No source file selected or file is not saved')

		r, c = view.rowcol(view.sel()[0].begin())
		return file, r + 1, c + 1

	def current_file_line(self) -> tuple[str, int]:
		line, col, _ = self.current_file_line_column()
		return line, col
