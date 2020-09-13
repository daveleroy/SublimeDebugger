from ..typecheck import*
from ..import core

from .adapter import Configuration, ConfigurationCompound
from .util import get_setting

import sublime
import json

class DebuggerProject(core.disposables):
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

		self.name = project_name
		self.window = window
		self.on_updated: core.Event[None] = core.Event()

		self.compounds: List[ConfigurationCompound] = []
		self.configurations: List[Configuration] = []

		self.external_terminal_kind = 'platform'
		self.ui_scale = 12
		self.bring_window_to_front_on_pause = False


		# add the empty debugger configurations settings if needed
		data = window.project_data() or {}
		data.setdefault('settings', {}).setdefault('debug.configurations', [])
		window.set_project_data(data)

		self.settings = sublime.load_settings('debugger.sublime-settings')
		self.settings_key = "DebuggerProject." + str(id(self))
		self.settings.add_on_change(self.settings_key, self.reload)

		self.reload()

	def dispose(self):
		super().dispose()
		self.settings.clear_on_change(self.settings_key)
	@core.schedule
	async def open_project_configurations_file(self):
		view = await core.sublime_open_file_async(self.window, self.name)
		region = view.find('''"\s*debug.configurations''', 0)
		if region:
			view.show_at_center(region)

	def reload(self):
		core.log_info("ProjectConfiguration.reload")
		self.load_settings()
		self.load_configurations()
		self.on_updated()

	def load_settings(self):
		core.log_configure(
			log_info=get_setting(self.window.active_view(), 'log_info', False),
			log_errors=get_setting(self.window.active_view(), 'log_errors', True),
			log_exceptions=get_setting(self.window.active_view(), 'log_exceptions', True),
		)

		self.external_terminal_kind = get_setting(self.window.active_view(), 'external_terminal', self.external_terminal_kind)
		self.ui_scale = get_setting(self.window.active_view(), 'ui_scale', self.ui_scale)
		self.bring_window_to_front_on_pause = get_setting(self.window.active_view(), 'bring_window_to_front_on_pause', self.bring_window_to_front_on_pause)

	def load_configurations(self):
		data = self.window.project_data() or {}

		configurations = []
		configurations_json = data.setdefault('settings', {}).setdefault('debug.configurations', [])

		for index, configuration_json in enumerate(configurations_json):
			configuration = Configuration.from_json(configuration_json, index)
			configurations.append(configuration)

		self.configurations = configurations

		compounds = []
		compounds_json = data.setdefault('settings', {}).setdefault('debug.compounds', [])

		for index, compound_json in enumerate(compounds_json):
			compound = ConfigurationCompound.from_json(compound_json, index)
			compounds.append(compound)

		self.compounds = compounds

	def is_source_file(self, view: sublime.View) -> bool:
		return bool(self.source_file(view))

	def source_file(self, view: sublime.View) -> Optional[str]:
		if view.window() != self.window:
			return None

		return view.file_name()

	def extract_variables(self) -> dict:
		variables = self.window.extract_variables()
		variables["package"] = core.current_package()
		project = variables.get('project_path')
		if project:
			variables['workspaceFolder'] = project
		return variables

	def current_file_line_column(self) -> Tuple[str, int, int]:
		view = self.window.active_view()
		file = self.source_file(view)
		if not file or not view:
			raise core.Error("No source file selected, no view open or file is not saved")

		r, c = view.rowcol(view.sel()[0].begin())
		return file, r + 1, c + 1

	def current_file_line(self) -> Tuple[str, int]:
		line, col, _ = self.current_file_line_column()
		return line, col
