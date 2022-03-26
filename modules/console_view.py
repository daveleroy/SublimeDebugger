from __future__ import annotations

import sublime_plugin
from .typecheck import *

from .import core
from .import dap
from .import ui
from .settings import Settings

import re
import sublime

class ConsoleView:
	console_views: ClassVar[Dict[int, ConsoleView]] = {}

	def __init__(self, window: sublime.Window, name: str, on_close: Callable[[], None]|None = None):
		self.on_escape: core.Event[None] = core.Event()
		self.on_input: core.Event[str] = core.Event()

		DebuggerConsoleLayoutPreWindowHooks(window).run()
		view = window.new_file(flags=sublime.SEMI_TRANSIENT)
		DebuggerConsoleLayoutPostViewHooks(view).run()

		self.on_close = on_close
		self.window = window
		self.view = view
		self.name = name
		self.on_pre_view_closed_handle = core.on_pre_view_closed.add(self.view_closed)
		self.view.set_name(name)
		
		ConsoleView.console_views[self.view.id()] = self

		self.type: None|str = None
		self.phantoms: list[ui.Phantom] = []
		self.placeholder_id = 0

		self.view.assign_syntax('Packages/Debugger/Commands/DebuggerConsole.sublime-syntax')
		self.view.set_scratch(True)

		settings = self.view.settings()
		settings.set('line_numbers', False)
		settings.set('gutter', False)
		settings.set('font_size', Settings.ui_scale)
		settings.set('draw_unicode_white_space', 'none')
		settings.set('fade_fold_buttons', False)
		settings.set('scroll_past_end', False)

		settings.set('auto_complete_selector', 'debugger.console')
		settings.set('debugger.console', True)

		self.clear()
	
	def close(self):
		if not self.is_closed:
			self.view.close()

	@property
	def is_closed(self):
		return not self.view.is_valid()

	def view_closed(self, view: sublime.View):
		if view == self.view:
			sublime.set_timeout(self.dispose, 0)

	def dispose(self):
		self.clear_phantoms()
		try: del ConsoleView.console_views[self.view.id()]
		except: ...

		self.close()
		if self.on_close: self.on_close()

	def ensure_new_line(self, text: str, at: int|None = None):
		if at is None:
			at = self.at()

		if at != 0 and self.view.substr(at -1) != '\n':
			text = '\n' + text

		return text

	def on_enter(self):
		def edit(edit: sublime.Edit):
			edit_point = self.input_region().b
			text = self.view.substr(sublime.Region(edit_point, self.view.size()))
			self.view.erase(edit, sublime.Region(edit_point, self.view.size()))

			if text:
				self.on_input(text)
				self.write(self.ensure_new_line('❯ ' + text) + '\n', 'comment')

		core.edit(self.view, edit)
	

	def clear_phantoms(self):
		for phantom in self.phantoms:
			phantom.dispose()

		self.phantoms.clear()

	def input_region(self):
		if regions := self.view.get_regions('input'):
			region = regions[0]
			requires_new_line = self.view.substr(region.a - 1) != '\n'
		else:
			region = None
			requires_new_line = False

		if requires_new_line:
			marker = '\n\u200c' + escape_codes_by_color['comment']['match'] + '❯\u200c '
		else:
			marker = '\u200c' + escape_codes_by_color['comment']['match'] + '❯\u200c '
		
		# if the size has not changed just assume the marker is correct...
		if region and region.size() == len(marker):
			return region

		def edit(edit: sublime.Edit):
			if region:
				self.view.erase(edit, region)
			size = self.view.size()
			self.view.insert(edit, size, marker)
			self.view.add_regions('input', [sublime.Region(size, size + len(marker))])

		core.edit(self.view, edit)
		return self.view.get_regions('input')[0]

	def refresh_input_region(self):
		self.input_region()

	def refresh_read_only(self):
		input_region = self.input_region()
		selection = self.view.sel()[0].a
		edit_point = input_region.b

		self.view.set_read_only(selection < edit_point)

	def clear(self):
		def edit(edit: sublime.Edit):
			self.view.erase(edit, sublime.Region(0, self.view.size()))
		core.edit(self.view, edit)

		self.type = None
		self.clear_phantoms()

	def at(self):
		return self.input_region().a

	def write_phantom_placeholder(self, type) -> Callable[[], int]:
		at = self.at()
		self.write('\n', type)

		id = self.placeholder_id
		self.placeholder_id += 1
		self.view.add_regions(f'placeholder_{id}', [sublime.Region(at, at)])
		return lambda: self.view.get_regions(f'placeholder_{id}')[0].a

	def write(self, text: str, type: str|None = None):
		self.dirty = True

		text = text.replace('\r\n', '\n')

		def replacement(x: Any):
			try:
				return escape_codes_by_code[x.group()]['match']
			except KeyError:
				return ''

		text = ansi_escape.sub(replacement, text)
		
		def escape_code():
			match = escape_codes_by_color.get(type)
			if not match:
				return '\u200c'

			return f'\u200c{match["match"]}'


		def edit(edit: sublime.Edit):
			self.view.set_read_only(False)
			nonlocal text
			pt = self.at()
			if self.type != type:
				# add a new line when switching types if one is not present
				text = self.ensure_new_line(text)
				pt += self.view.insert(edit, pt, escape_code() + text)
			else:
				pt += self.view.insert(edit, pt, text)

			# not really ideal behavior but scroll to the bottom if the selection is in the input region
			if sublime.Region(pt, self.view.size()).contains(self.view.sel()[0]):
				self.view.show(self.view.size(), animate=False)
			self.type = type
			
		core.edit(self.view, edit)

	def scroll_to_end(self):
		pt = self.at()
		if sublime.Region(pt, self.view.size()).contains(self.view.sel()[0]):
			self.view.show(self.view.size(), animate=False)




def _window_has_output_views(window: sublime.Window):
	for view in window.views():
		if view.settings().has('debugger.console_layout'):
			return True
	return False


class DebuggerConsoleViewEscapeCommand(sublime_plugin.TextCommand):
	def run(self, edit: sublime.Edit):
		print("DebuggerConsoleViewEscapeCommand")
		console = ConsoleView.console_views[self.view.id()]
		console.on_escape.post()

class DebuggerConsoleLayoutPreWindowHooks(sublime_plugin.WindowCommand):
	def run(self):
		if not _window_has_output_views(self.window):
			for command in Settings.console_layout_begin:
				self.window.run_command(command['command'],  args=command.get('args'))

		for command in Settings.console_layout_focus:
			self.window.run_command(command['command'],  args=command.get('args'))

class DebuggerConsoleLayoutPostViewHooks(sublime_plugin.TextCommand):
	def run(self):
		self.view.settings().set('debugger.console_layout', True)

class DebuggerConsoleLayoutPostWindowHooks(sublime_plugin.WindowCommand):
	def run(self):
		def run():
			if not _window_has_output_views(self.window):
				for command in Settings.console_layout_end:
					self.window.run_command(command['command'],  args=command.get('args'))

		sublime.set_timeout(run, 0)

class DebuggerConsoleViewEventListener(sublime_plugin.ViewEventListener):
	@classmethod
	def is_applicable(cls, settings: sublime.Settings):
		return settings.has('debugger.console')

	def __init__(self, view: sublime.View) -> None:
		super().__init__(view)
		try:
			self.console = ConsoleView.console_views[self.view.id()]
		except KeyError:
			core.error('Closing Debugger Console View it is not attached to a console')
			
			window = view.window()
			if window:
				DebuggerConsoleLayoutPostWindowHooks(window).run()

			view.close()


	def on_pre_close(self):
		window = self.view.window()
		if window:
			DebuggerConsoleLayoutPostWindowHooks(window).run()

	def on_close(self):
		if self.console:
			self.console.dispose()

	def on_query_completions(self, prefix: str, locations: list[int]) -> Any:
		from .debugger import Debugger

		debugger = Debugger.get(self.view)
		if not debugger or not debugger.is_active:
			return

		edit_point = self.console.input_region().b
		text = self.view.substr(sublime.Region(edit_point, self.view.size()))
		col = (self.view.sel()[0].a - edit_point) + 1

		completions = sublime.CompletionList()

		@core.schedule
		async def fetch():
			items: list[sublime.CompletionItem] = []
			for completion in await debugger.active.completions(text, col):
				if completion.type == 'method' : kind = sublime.KIND_FUNCTION
				elif completion.type == 'function': kind = sublime.KIND_FUNCTION
				elif completion.type == 'constructor': kind = sublime.KIND_FUNCTION
				elif completion.type == 'field': kind = sublime.KIND_VARIABLE
				elif completion.type == 'variable': kind = sublime.KIND_VARIABLE
				elif completion.type == 'class': kind = sublime.KIND_TYPE
				elif completion.type == 'interface': kind = sublime.KIND_TYPE
				elif completion.type == 'module': kind = sublime.KIND_NAMESPACE
				elif completion.type == 'property': kind = sublime.KIND_VARIABLE
				elif completion.type == 'enum': kind = sublime.KIND_TYPE
				elif completion.type == 'keyword': kind = sublime.KIND_KEYWORD
				elif completion.type == 'snippet': kind = sublime.KIND_SNIPPET
				else: kind = sublime.KIND_AMBIGUOUS

				item = sublime.CompletionItem(
					trigger=completion.text or completion.label,
					annotation=completion.detail or "",
					completion=completion.text or completion.label,
					completion_format=sublime.COMPLETION_FORMAT_TEXT,
					kind=kind
				)
				items.append(item)
			completions.set_completions(items)

		fetch()
		return completions


	def on_modified(self) -> None:
		self.console.refresh_input_region()

	def on_selection_modified(self):
		self.console.refresh_read_only()		

	def on_text_command(self, command_name: str, args: Any):
		if command_name == 'insert' and args['characters'] == '\n':
			console = ConsoleView.console_views[self.view.id()]
			console.on_enter()
			return ('noop')


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
	{
		'color': 'comment',
		'escape': [],
		'scope': 'comment.debugger',
		'match': '\u200b\u200b\u200b\u200b\u200b\u200b\u200b',
	},
]

escape_codes_by_code: dict[str|None, Any] = {}
escape_codes_by_color: dict[str|None, Any] = {}

for item in escape_codes:
	escape_codes_by_color[item['color']] = item

	for escape in item['escape']:
		escape_codes_by_code[escape] = item

def generate_console_syntax():
	yaml = '''%YAML 1.2
---
hidden: true
scope: debugger.console
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