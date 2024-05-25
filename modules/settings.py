from __future__ import annotations
from typing import Callable, ForwardRef, Generic, Any, TypeVar
from . import core

import sublime

T = TypeVar('T')
class Setting(Generic[T], object):
	def __init__(self, key: str, default: T, description: str = '', visible = True, schema: Any|None = None) -> None:
		self.key = key
		self.default = default
		self.description = description
		self.visible = visible
		self.schema = schema

	@property
	def value(self)  -> T:
		return SettingsRegistery.settings.get(self.key, self.default)

	@value.setter
	def value(self, value: T):
		return SettingsRegistery.settings.set(self.key, value)

	def __get__(self, obj, objtype=None) -> T:
		return SettingsRegistery.settings.get(self.key, self.default)

	def update(self, value: T):
		SettingsRegistery.settings.set(self.key, value)
		SettingsRegistery.save()

	def __set__(self, obj, value: T):
		SettingsRegistery.settings.set(self.key, value)
		SettingsRegistery.save()


class Settings:
	open_at_startup = Setting[bool] (
		key='open_at_startup',
		default=True,
		description='Open the debugger automatically when a project that is set up for debugging'
	)

	always_keep_visible = Setting[bool] (
		key='always_keep_visible',
		default=False,
		description='Always keep the debugger panel visible'
	)

	font_size = Setting['float|None'] (
		key='font_size',
		default=None,
		description='Change the font size of the debugger ui. Defaults to the font size in your preferences.'
	)

	internal_font_scale = Setting[float] (
		key='internal_font_scale',
		default=1,
		description='Expected values of around 0.95 to 1.05. Only change this if the text/images/content are not aligning correctly within the panels (could cause the last panel to be clipped).'
	)

	internal_width_modifier = Setting[float] (
		key='internal_width_modifier',
		default=0,
		description='Expected values of around 0 to -5. Only change this if the size of the panels is too large and the last panel is cropped off (adjust internal_font_scale first if text/images/content are not aligned correctly). Negative values make the panels smaller. Postive make them bigger.'
	)

	external_terminal = Setting[str] (
		key='external_terminal',
		default='terminus',
		description='''
		Which external terminal should be used when an adapter requests an external terminal
		"platform" (default) uses Terminal on MacOS, CMD (Not tested) on Windows, (Unimplemented) on Linux
		"terminus" Opens a new terminal view using terminus. The terminus package must be installed https://github.com/randy3k/Terminus
		'''
	)

	minimum_console_height = Setting[int] (
		key='minimum_console_height',
		default=10,
		description='''
		Controls the minimum height of the debugger output panels in lines
		'''
	)

	bring_window_to_front_on_pause: bool = False

	development = Setting[bool] (
		key='development',
		default=False,
		description='Additional console logs and some new features are locked behind this flag'
	)

	node = Setting['str|None'] (
		key='node',
		default=None,
		description='Sets a specific path for node if not set adapters that require node to run will use whatever is in your path'
	)


	integrated_output_panels = Setting['dict[str, dict[str, str]]'] (
		key='integrated_output_panels',
		default={},
		description=
		'''
		Output panels outside of the debugger can be integrated into the tabbed debugger interface (note: In some cases output panels may cause issues and not work correctly depending on who owns them)
		An example for interating the Diagnostics panel of LSP and a Terminus output panel.

		"integrated_output_panels": {
			"diagnostics": {
				"name": "Diagnostics",
			},
			"Terminus": {
				"name": "Terminal",
				"position": "bottom",
			}
		}
		'''
	)

	installed_packages = Setting['list[str]'] (
		key='installed_packages',
		default=[],
		description='Some debug adapters require certain packages to be installed via package control. If you have installed these package outside of package control then you can add them to this list and they will be treated as if they are installed.'
	)

	global_debugger_configurations = Setting['list[Any]'] (
		key='global_debugger_configurations',
		default=[],
		description='''
		Global debugger configurations that are accessible from every project
		''',
		schema={
			'type': 'array',
			'items': { '$ref': 'sublime://settings/debugger#/definitions/debugger_configuration' },
		}
	)

	global_debugger_tasks = Setting['list[Any]'] (
		key='global_debugger_tasks',
		default=[],
		description='''
		Global debugger tasks that are accessible from every project
		''',
		schema={
			'type': 'array',
			'items': { '$ref': 'sublime://settings/debugger#/definitions/debugger_task' },
		}
	)

	global_debugger_compounds = Setting['list[Any]'] (
		key='global_debugger_compounds',
		default=[],
		description='''
		Global debugger compounds that are accessible from every project
		''',
		schema={
			'type': 'array',
			'items': { '$ref': 'sublime://settings/debugger#/definitions/debugger_compound' },
		}
	)

# Settings __set__ method will not get called on a class so just override the class with an instance of itself...
Settings = Settings() # type: ignore

class SettingsRegistery:
	settings: sublime.Settings

	@staticmethod
	def initialize(on_updated: Callable[[], None]):
		SettingsRegistery.settings = sublime.load_settings('Debugger.sublime-settings')
		SettingsRegistery.settings.clear_on_change('debugger_settings')
		SettingsRegistery.settings.add_on_change('debugger_settings', on_updated)

	@staticmethod
	def save():
		sublime.save_settings('Debugger.sublime-settings')

	@staticmethod
	def schema():
		import gc
		import typing
		import textwrap

		properties = {}
		for setting in gc.get_objects():
			if not isinstance(setting, Setting):
				continue

			t = typing.get_args(setting.__orig_class__)[0] #type: ignore

			schema: dict[str, Any] = {}
			if setting.schema:
				schema = setting.schema
			elif t == bool:
				schema = { 'type': 'boolean' }
			elif t == int:
				schema = { 'type': 'number' }
			elif t == ForwardRef('int|None'):
				schema = { 'type': ['number', 'null'] }
			elif t == float:
				schema = { 'type': 'number' }
			elif t == ForwardRef('float|None'):
				schema = { 'type': ['number', 'null'] }
			elif t == str:
				schema = { 'type': 'string' }
			elif t == ForwardRef('str|None'):
				schema = { 'type': ['string', 'null'] }
			else:
				schema = { 'type': ['object', 'array'] }

			schema['description'] = textwrap.dedent(setting.description).strip().split('\n')[0]
			properties[setting.key] = schema

		return {
			'additionalProperties': False,
			'properties': properties
		}

	@staticmethod
	def generate_settings():
		import gc
		import json
		import textwrap

		output = '{\n'

		for setting in gc.get_objects():
			if not isinstance(setting, Setting):
				continue

			if not setting.visible: continue

			lines = textwrap.dedent(setting.description).strip().split('\n')
			comment = ''
			for line in lines:
				# skip leading empty lines
				if not comment and not line: continue

				comment += f'\t// {line}\n'

			output += comment
			output += f'\t{json.dumps(setting.key)}: {json.dumps(setting.default)},'
			output += '\n\n'


		output += '}'

		with open(f'{core.package_path()}/Debugger.sublime-settings', 'w') as f:
			f.write(output)
