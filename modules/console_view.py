from __future__ import annotations
from .typecheck import *

from .import core
from .import ui
from .settings import Settings

import re
import sublime


class ConsoleView:
	def __init__(self, view: sublime.View):
		self.view = view
		self.type: None|str = None
		self.phantoms: list[ui.Phantom] = []
		self.should_restore_single_panel = False

		self.view.assign_syntax('Packages/Debugger/Commands/DebuggerConsole.sublime-syntax')
		settings = self.view.settings()
		settings.set('line_numbers', False)
		settings.set('gutter', False)
		settings.set('font_size', Settings.ui_scale)
		settings.set('draw_unicode_white_space', 'none')
		settings.set('fade_fold_buttons', False)

		settings.set('scroll_past_end', False)
		self.view.set_read_only(True)
		self.view.set_scratch(True)

	def dispose(self):
		self.clear_phantoms()

	def clear_phantoms(self):
		for phantom in self.phantoms:
			phantom.dispose()

		self.phantoms.clear()

	def clear(self):
		view = self.view
		self.type = None
		self.view.set_read_only(False)
		core.edit(view, lambda edit: view.erase(edit, sublime.Region(0, view.size())))
		self.view.set_read_only(True)
		self.clear_phantoms()

	def at(self):
		return self.view.size()

	def write_phantom_placeholder(self) -> int:
		view = self.view
		view.set_read_only(False)
		view.run_command('append', {
			'characters': '\n',
			'force': True,
			'scroll_to_end': True
		})
		view.set_read_only(True)
		return view.size() - 1

	def write_phantom(self, item: ui.div, at: int, index: int = 0):
		view = self.view
		at = view.size() if at is None else at
		self.phantoms.append(ui.Phantom(item, view, sublime.Region(at, at + index), layout=sublime.LAYOUT_INLINE))

	def write(self, text: str, type: str = '', item: ui.div|None = None):
		self.dirty = True
		self.view.set_read_only(False)

		text = text.replace('\r\n', '\n')

		def replacement(x: Any):
			try:
				return escape_codes_by_code[x.group()]['match']
			except KeyError:
				return ''

		text = ansi_escape.sub(replacement, text)

		sequences_for_types = {
			'debugger.error': escape_codes_by_color['red']['match'],
			'stderr': escape_codes_by_color['red']['match'],
			'debugger.info': escape_codes_by_color['blue']['match'],
		}

		if self.type != type:
			# add a new line when switching types if one is not present
			if self.type and self.view.substr(self.view.size() - 1) != '\n':
				text = '\n' + text

			self.view.run_command('append', {
				'characters': '\u200c' + sequences_for_types.get(type, ''),
				'force': True,
				'scroll_to_end': True
			})

		self.type = type
		offset = -1


		self.view.run_command('append', {
			'characters': text,
			'force': True,
			'scroll_to_end': True
		})

		self.view.set_read_only(True)

		if item:
			at = self.view.size() + offset
			self.phantoms.append(ui.Phantom(item, self.view, sublime.Region(at, at)))

# from https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')

escape_codes: list[dict[str, Any]] = [
	{
		'color': 'foreground',
		'escape': ['\u001b[30m', '\u001b[37m', '\u001b[39m', '\u001b[0m', '\u001b[90m'],
		'match': '\u200c',
	},
	{
		'color': 'red',
		'escape': ['\u001b[31m', '\u001b[91m'],
		'scope': 'region.redish.debugger region.background.debugger',
		'match': '\u200b',
	},
	{
		'color': 'green',
		'escape': ['\u001b[32m', '\u001b[92m'],
		'scope': 'region.greenish.debugger region.background.debugger',
		'match': '\u200b\u200b',
	},
	{
		'color': 'yellow',
		'escape': ['\u001b[33m', '\u001b[93m'],
		'scope': 'region.yellowish.debugger region.background.debugger',
		'match': '\u200b\u200b\u200b',
	},
	{
		'color': 'blue',
		'escape': ['\u001b[34m', '\u001b[94m'],
		'scope': 'region.bluish.debugger region.background.debugger',
		'match': '\u200b\u200b\u200b\u200b',
	},
	{
		'color': 'magenta',
		'escape': ['\u001b[35m', '\u001b[95m'],
		'scope': 'region.purplish.debugger region.background.debugger',
		'match': '\u200b\u200b\u200b\u200b\u200b',
	},
	{
		'color': 'cyan',
		'escape': ['\u001b[36m', '\u001b[96m'],
		'scope': 'region.cyanish.debugger region.background.debugger',
		'match': '\u200b\u200b\u200b\u200b\u200b\u200b',
	},
]

escape_codes_by_code: dict[str, Any] = {}
escape_codes_by_color: dict[str, Any] = {}

for item in escape_codes:
	escape_codes_by_color[item['color']] = item

	for escape in item['escape']:
		escape_codes_by_code[escape] = item

def generate_console_syntax():
	yaml = '''%YAML 1.2
---
hidden: true
scope: output.debugger.log
name: Debugger Console

contexts:
	main:
'''

	for item in reversed(escape_codes):
		scope = item.get('scope')
		if not scope:
			continue

		yaml += f'''		- match: '{item['match']}'
			scope: {scope}
			push:
				- meta_scope: {scope}
				- match: '\u200c'
					scope: {scope}
					pop: true
'''
	return yaml.replace('\t', '  ')