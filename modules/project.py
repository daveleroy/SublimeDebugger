from __future__ import annotations
from .typecheck import *

from .import core
from .dap import Configuration, ConfigurationCompound, Task
from .settings import Settings

import sublime
import os

class Project:
	def __init__(self, window: sublime.Window):
		super().__init__()

		# ensure we are being run inside a sublime project
		# if not prompt the user to create one
		project_name = window.project_file_name()
		while not project_name:
			r = sublime.ok_cancel_dialog("Debugger requires a sublime project. Would you like to create a new sublime project?", "Save Project As...")
			if r:
				window.run_command('save_project_and_workspace_as')
			else:
				raise core.Error("Debugger must be run inside a sublime project")

			project_name = window.project_file_name()

		self.project_name = project_name
		self.window = window
		self.on_updated: core.Event[None] = core.Event()

		self.tasks: list[Task] = []
		self.compounds: list[ConfigurationCompound] = []
		self.configurations: list[Configuration] = []
		self.configuration_or_compound: Optional[Union[Configuration, ConfigurationCompound]] = None

		self.external_terminal_kind = 'platform'
		self.ui_scale = 12
		self.bring_window_to_front_on_pause = False

		# add the empty debugger configurations settings if needed
		data: dict[str, Any] = window.project_data() or {}
		data.setdefault('debugger_configurations', [])
		window.set_project_data(data)
		self.reload()

	def dispose(self):
		...

	@property
	def name(self) -> str:
		if self.configuration_or_compound:
			return self.configuration_or_compound.name

		return self.project_name

	def into_json(self) -> dict[str, Any]:
		return {
			'configuration_name': self.configuration_or_compound and self.configuration_or_compound.name,
			'configuration_id_ish': self.configuration_or_compound and self.configuration_or_compound.id_ish,
		}

	def load_from_json(self, json: dict[str, Any]) -> Optional[Union[Configuration, ConfigurationCompound]]:
		configuration_name: str|None = json.get('configuration_name')
		configuration_id_ish: str|None = json.get('configuration_id_ish')

		if configuration_name and configuration_id_ish:
			self.load_configuration(configuration_name, configuration_id_ish)

	def load_configuration(self, configuration_name: str, configuration_id_ish: str):
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

		self.configuration_or_compound = find_matching_configuration()

	def get_task(self, name: str) -> Task:
		for task in self.tasks:
			if task.name == name:
				return task
		raise core.Error(f'Unable to find task with name "{name}"')

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
					raise core.Error(f'Unable to find configuration with name "{configuration_name}" while evaluating compound "{self.configuration_or_compound.name}"')

			return configurations

		if isinstance(self.configuration_or_compound, Configuration):
			return [self.configuration_or_compound]

		return []

	@core.schedule
	async def open_project_configurations_file(self):
		view = await core.sublime_open_file_async(self.window, self.project_name)

		region = view.find(r'debugger_configurations', 0)
		if region:
			view.show_at_center(region)

	def reload(self):
		core.info("ProjectConfiguration.reload")
		self.load_settings()
		self.load_configurations()
		self.on_updated.post()

	def load_settings(self):
		core.log_configure(
			log_info= Settings.log_info,
			log_errors= Settings.log_errors,
			log_exceptions= Settings.log_exceptions,
		)

		self.external_terminal_kind = Settings.external_terminal
		self.ui_scale = Settings.ui_scale
		self.bring_window_to_front_on_pause = Settings.bring_window_to_front_on_pause


	def configurations_from_project(self, project_data: Any, key: str) -> list[Any]:
		configurations: list[Any] = []
		for configuration_or_file in project_data.get(key, []):
			# allow putting in string values here that point to other project files...
			# this is for testing the /examples directory easily...
			if isinstance(configuration_or_file, str):
				configurations.extend(self.configurations_from_project_file(configuration_or_file, key))
			else:
				configurations.append(configuration_or_file)

		return configurations

	def configurations_from_project_file(self, path: str, key: str) -> list[Any]:
		if not os.path.isabs(path):
			path = os.path.join(self.window.extract_variables()['project_path'], path)

		project_path = os.path.dirname(path)
		with open(path , 'r') as file:
			contents = file.read()

		project_json = sublime.decode_value(contents) or {}		
		json: list[Any] = project_json.get(key, [])
		for configuration in json:
			configuration['$'] = {
				'project_path': project_path
			}
		return json
		

	def load_configurations(self):
		data: dict[str, Any] = self.window.project_data() or {}

		# check for old format and suggest a fixit
		settings: dict[str, Any] = data.get('settings', {})
		if 'debug.configurations' in settings:
			r = sublime.ok_cancel_dialog("Debugger configurations should now be added as 'debugger_configurations' at the root level of the project. Would you like Debugger to automatically update your project file.", "Update Project")
			if r:
				data['debugger_configurations'].extend(settings['debug.configurations'])
				del settings['debug.configurations']

				# make this update after we are out of load_configurations otherwise weird stuff happens...
				# probably something to do with sublime project event updates
				@core.schedule
				async def update():
					self.window.set_project_data(data)

				update()


		tasks: list[Task] = []
		configurations: list[Configuration] = []
		compounds: list[ConfigurationCompound] = []

		for task_json in self.configurations_from_project(data, 'debugger_tasks'):
			task = Task.from_json(task_json)
			tasks.append(task)

		for configuration_json in self.configurations_from_project(data, 'debugger_configurations'):
			configuration = Configuration.from_json(configuration_json, len(configurations))
			configurations.append(configuration)

		for compound_json in self.configurations_from_project(data, 'debugger_compounds'):
			compound = ConfigurationCompound.from_json(compound_json, len(compounds))
			compounds.append(compound)

		self.configurations = configurations
		self.compounds = compounds
		self.tasks = tasks

		# reselect the old configuration
		if self.configuration_or_compound:
			self.load_configuration(self.configuration_or_compound.name, self.configuration_or_compound.id_ish)

	def is_source_file(self, view: sublime.View) -> bool:
		return bool(self.source_file(view))

	def source_file(self, view: sublime.View) -> str|None:
		if view.window() != self.window:
			return None

		return view.file_name()

	def extract_variables(self):
		variables: dict[str, str] = self.window.extract_variables()

		# patch in some vscode variables
		if folder := variables['folder']:
			variables['workspaceFolder'] = folder
			variables['workspaceRoot'] = folder
		return variables

	def current_file_line_column(self) -> Tuple[str, int, int]:
		view = self.window.active_view()
		if not view:
			raise core.Error("No open view")

		file = self.source_file(view)
		if not file:
			raise core.Error("No source file selected or file is not saved")

		r, c = view.rowcol(view.sel()[0].begin())
		return file, r + 1, c + 1

	def current_file_line(self) -> Tuple[str, int]:
		line, col, _ = self.current_file_line_column()
		return line, col
