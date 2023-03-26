from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable

import sublime

from .import core
from .import ui
from .import dap

from .views.variable import VariableView

from .ansi import ansi_colorize

from .debugger_protocol_panel import DebuggerProtocolPanel
from .debugger_output_panel import DebuggerOutputPanel

if TYPE_CHECKING:
	from .debugger import Debugger

class DebuggerConsoleOutputPanel(DebuggerOutputPanel, dap.Console):
	def __init__(self, debugger: Debugger) -> None:
		super().__init__(debugger, 'Debugger Console', name='Console', show_tabs=True, remove_last_newline=True)

		self.on_input = core.Event[str]()
		self.on_navigate = core.Event[dap.SourceLocation]()
		self.debugger = debugger

		self.protocol = DebuggerProtocolPanel(debugger)

		self.view.assign_syntax(core.package_path_relative('contributes/Syntax/DebuggerConsole.sublime-syntax'))
		self.color: str|None = None
		self.phantoms = []
		self.input_size = 0

		self.indent = ''
		self.forced_indent = ''

		self._history_offset = 0
		self._history = []

		self._annotation_id = 0

		self._last_output_event: dap.OutputEvent|None = None
		self._last_output_event_annotation_id = 0
		self._last_output_event_count = 0

		settings = self.view.settings()
		settings.set('context_menu', 'DebuggerWidget.sublime-menu')
		settings.set('auto_complete_selector', 'debugger.console')
		settings.set('debugger.console', True)

		self.clear()

	def edit(self, fn: Callable[[sublime.Edit], Any]):
		is_read_only = self.view.is_read_only()
		if is_read_only:
			self.view.set_read_only(False)
			core.edit(self.view, fn)
			self.view.set_read_only(True)
		else:
			core.edit(self.view, fn)

	def program_output(self, session: dap.Session, event: dap.OutputEvent):
		type = event.category or 'console'
		if type == 'telemetry':
			return

		source = None
		if event.source:
			source = dap.SourceLocation(event.source, event.line)

		color_for_type: dict[str|None, str|None] = {
			'stderr': 'red',
			'stdout': 'foreground',
			'important': 'magenta',
		}

		color = color_for_type.get(type) or 'blue'

		if event.group == 'end':
			self.end_indent()

		if event.variablesReference:
			self.write(f'\u200b\n', color, ensure_new_line=True, ignore_indent=False)
			placeholder = self.add_annotation(self.at() - 1, source)

			async def appendVariabble(variablesReference: int) -> None:
				try:
					variables = await session.get_variables(variablesReference, without_names=True)
					for variable in variables:
						at = self.annotation_region(placeholder).a
						self.write_variable(variable, at, variable==variables[-1])

				# if a request is cancelled it is because the debugger session ended
				# In some cases the variable cannot be fetched since the debugger session was terminated because of the exception
				# However the exception message is actually important and needs to be shown to the user...
				except core.CancelledError:
					print('Unable to fetch variables: Cancelled')
					# todo: this should be inserted into the place the phantom was going to be
					# self.append_text(event.category or 'console', self.indent + event.output, event.source, event.line)

			core.run(appendVariabble(event.variablesReference))

		elif event.output:
			if self.is_output_identical_to_previous(event):
				self._last_output_event_count += 1
				self._last_output_event_annotation_id = self.add_annotation(self.at() - 1, source, self._last_output_event_count, self._last_output_event_annotation_id)
			else:
				self._last_output_event = event
				self._last_output_event_count = 1

				self.write(event.output, color, ignore_indent=False)
				if event.source:
					self._last_output_event_annotation_id = self.add_annotation(self.at() - 1, source)
				else:
					self._last_output_event_annotation_id = None

		if event.group == 'start' or event.group == 'startCollapsed':
			self.start_indent()

	def is_output_identical_to_previous(self, event: dap.OutputEvent):
		if not self._last_output_event:
			return False

		if event.group:
			return False

		if self._last_output_event.group:
			return False

		return self._last_output_event.category == event.category and self._last_output_event.output == event.output

	def start_indent(self, forced: bool = False):
		if forced:
			self.forced_indent += '\t'
		else:
			self.indent += '\t'

	def end_indent(self, forced: bool = False):
		if forced:
			self.forced_indent = self.forced_indent[:-1]
		else:
			self.indent = self.indent[:-1]

	def scroll_to_end(self):
		super().scroll_to_end()
		self.window.focus_view(self.view)

	def at(self):
		# there is always a single invisible character at the end of the content otherwise every single write causes the phantom to be out of position and require re-rendering
		if input := self.input():
			return max(input.a - 1, 0)
		return max(self.view.size() - 1, 0)

	def write(self, text: str, color: str|None, ensure_new_line=False, ignore_indent: bool = True):

		if not ignore_indent and self.indent:
			text = self.indent + text

		if self.forced_indent:
			text = self.forced_indent + text

		# if we are changing color we want it on its own line
		if ensure_new_line or self.color != color:
			text = self.ensure_new_line(text)

		self.edit(lambda edit: self.view.insert(edit, self.at(), ansi_colorize(text, color, self.color)))
		self.color = color

	def write_variable(self, variable: dap.Variable, at: int, last: bool = True):
		html = f'''
			<style>
			html {{
				background-color: var(--background);
			}}
			a {{
				color: color(var(--foreground) alpha(0.25));
				text-decoration: none;
				padding-left: 0.0rem;
				padding-right: 0.0rem;
			}}
			</style>
			<body id="debugger">
				<a href="">{ui.html_escape(f'❯')}</a>
			</body>
		'''

		# phantom_at = at + len(indent)

		def on_navigate(path: str):
			component = VariableView(self.debugger, variable, children_only=True)
			component.set_expanded()
			popup = ui.Popup(self.view, at)[
				component
			]

		def edit(edit: sublime.Edit):
			# remove trailing \n if it exists since we already inserted a newline to place this variable in
			content = (variable.value or variable.name or '{variable}').rstrip('\n')
			if not last:
				content += ' '

			self.view.insert(edit, at, content)

		self.edit(edit)

		phantom = ui.RawPhantom(self.view, sublime.Region(at, at), html, on_navigate=on_navigate)
		self.phantoms.append(phantom)

	def add_annotation(self, at: int, source: dap.SourceLocation|None = None, count: int|None = None, annotation_id: int|None = None):

		if not annotation_id:
			self._annotation_id += 1
			annotation_id = self._annotation_id

		if source or count and count > 1:

			if source:
				on_navigate = lambda _: self.on_navigate(source)
				source_html = f'<a href="">{source.name}</a>'
			else:
				on_navigate = None
				source_html = ''

			count_html = f'<span>{count}</span>' if count else ''

			html = f'''
			<style>
				html {{
					background-color: var(--background);
				}}
				a {{
					color: color(var(--foreground) alpha(0.33));
					text-decoration: none;
				}}
				span {{
					color: color(var(--foreground) alpha(0.66));
					background-color: color(var(--accent) alpha(0.5));
					padding-right: 1.1rem;
					padding-left: -0.1rem;
					border-radius: 0.5rem;
				}}
			</style>
			<body id="debugger">
				<div>
					{count_html}
					{source_html}
				</div>
			</body>
			'''

			self.view.add_regions(f'an{annotation_id}', [sublime.Region(at, at)], annotation_color="#fff0", annotations=[html], on_navigate=on_navigate)
		else:
			self.view.add_regions(f'an{annotation_id}', [sublime.Region(at, at)])

		return annotation_id

	def annotation_region(self, id: int):
		return self.view.get_regions(f'an{id}')[0]

	def clear(self):
		self.indent = ''
		self.forced_indent = ''
		self.protocol.clear()
		self.dispose_phantoms()
		self._last_output_event = None
		self.color = None
		self.edit(lambda edit: self.view.replace(edit, sublime.Region(0, self.view.size()), '\u200b'))
		self.view.set_read_only(True)

	def on_selection_modified(self):
		input = self.input()
		if not input:
			self.view.set_read_only(True)
			return

		at = input.a - 1
		for region in self.view.sel():
			if region.a <= at:
				self.view.set_read_only(True)
				return

		self.view.set_read_only(False)

	def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool|None:
		self.set_input_mode()
		return None

	def on_post_text_command(self, command_name: str, args: Any):
		if command_name == 'copy':
			sublime.set_clipboard(sublime.get_clipboard().replace('\u200c', '').replace('\u200b', ''))

	def on_text_command(self, command_name: str, args: Any): #type: ignore
		if command_name == 'insert' and args['characters'] == '\n' and self.enter():
			return ('noop')

		# I have no idea why left_delete breaks layout_extent when getting the height of the content + phantom but it does...
		# this causes every left_delete to make the spacer at the bottom larger and larger
		# performing our own left_delete seems to fix this
		if command_name == 'left_delete':
			core.edit(self.view, lambda edit: self.view.erase(edit, sublime.Region(self.view.size() -1 ,self.view.size())))
			return ('noop')

		if not self.view.is_auto_complete_visible() and command_name == 'move' and args['by'] =='lines':
			self.set_input_mode()
			if args['forward']:
				self.autofill(-1)
			else:
				self.autofill(1)
			return ('noop')

	def on_query_completions(self, prefix: str, locations: list[int]) -> Any:
		input = self.input()
		if not input: return

		text = self.view.substr(sublime.Region(input.b, self.view.size()))
		col = (locations[0] - input.b)
		completions = sublime.CompletionList()

		items: list[sublime.CompletionItem] = []

		for fill in self._history:
			items.append(sublime.CompletionItem.command_completion(
					trigger=fill,
					annotation='',
					kind=sublime.KIND_SNIPPET,
					command='insert',
					args= {
						'characters': fill
					}
				))

		@core.run
		async def fetch():
			try:
				if not self.debugger.is_active or not self.debugger.active.capabilities.supportsCompletionsRequest:
					raise core.CancelledError

				for completion in await self.debugger.active.completions(text, col):
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
					else: kind = sublime.KIND_VARIABLE

					item = sublime.CompletionItem.command_completion(
						trigger=completion.text or completion.label,
						annotation=completion.detail or '',
						kind=kind,
						command='insert',
						args= {
							'characters': completion.text or completion.label
						}
					)

					items.append(item)

			except core.Error as e:
				core.debug('Unable to fetch completions:', e)

			except core.CancelledError:
				...

			completions.set_completions(items, sublime.INHIBIT_EXPLICIT_COMPLETIONS|sublime.INHIBIT_REORDER|sublime.INHIBIT_WORD_COMPLETIONS)

		fetch()
		return completions

	def on_deactivated(self):
		self.clear_input_mode()

	def input(self):
		regions = self.view.get_regions('input')
		if not regions:
			return None
		region = regions[0]

		if region.size() != self.input_size:
			self.view.erase_regions('input')
			self.edit(lambda edit: self.view.erase(edit, region))
			return None

		return region

	def clear_input_mode(self):
		if input := self.input():
			self.view.erase_regions('input')
			self.edit(lambda edit: self.view.erase(edit, sublime.Region(input.a, self.view.size())))

	def set_input_mode(self):
		if input := self.input():
			sel = self.view.sel()
			end_of_input = input.b

			for region in sel:
				if region.a < end_of_input:
					self.view.set_read_only(False)
					self.scroll_to_end()
					return

			return

		a = self.view.size()

		def edit(edit):
			marker = '\n\u200c:' if a > 1 else '\u200c:'
			size = self.view.insert(edit, a, marker)
			self.input_size = size
			self.view.add_regions('input', [sublime.Region(a, a+size)])

		self.edit(edit)
		self.view.set_read_only(False)
		self.scroll_to_end()

	def enter(self):
		self.set_input_mode()
		input = self.input()
		if not input: return False

		text_region = sublime.Region(input.b, self.view.size())
		text = self.view.substr(text_region)
		if not text: return True

		self.edit(lambda edit: (
			self.view.erase(edit, text_region),
			self.view.sel().clear(),
			self.view.sel().add(self.view.size())
		))

		self.on_input(text)
		self.write(':' + text, 'comment', True)
		self._history_offset = 0
		self._history.append(text)
		return True


	def autofill(self, offset: int):
		self._history_offset += offset
		self._history_offset = min(max(0, self._history_offset), len(self._history))
		self.set_input_mode()
		input = self.input()
		if not input: return False

		text_region = sublime.Region(input.b, self.view.size())
		if self._history_offset:
			self.edit(lambda edit: (
				self.view.replace(edit, text_region, self._history[-self._history_offset]),
				self.view.sel().clear(),
				self.view.sel().add(self.view.size())
			))
		else:
			self.edit(lambda edit: (
				self.view.erase(edit, text_region),
				self.view.sel().clear(),
				self.view.sel().add(self.view.size())
			))



	def log(self, type: str, value: Any, source: dap.SourceLocation|None = None):
		if type == 'transport':
			self.protocol.log('transport', value)
		elif type == 'error-no-open':
			self.write(str(value).rstrip('\n'), 'red', ensure_new_line=True)
		elif type == 'error':
			self.write(str(value).rstrip('\n'), 'red', ensure_new_line=True)
			self.open()
		elif type == 'group-start':
			self.write(str(value), None, ensure_new_line=True)
			self.start_indent(forced=True)
		elif type == 'group-end':
			self.end_indent(forced=True)
			self.write(str(value), None, ensure_new_line=True)
		elif type == 'stdout':
			self.protocol.log('stdout', value)
			self.write(str(value), None)
		elif type == 'stderr':
			self.protocol.log('stderr', value)
			self.write(str(value), 'red')
		elif type == 'stdout':
			self.write(str(value), None)
		elif type == 'warn':
			self.write(str(value).rstrip('\n'), 'yellow', ensure_new_line=True)
		elif type == 'success':
			self.write(str(value).rstrip('\n'), 'green', ensure_new_line=True)
		else:
			self.write(str(value).rstrip('\n'), 'comment', ensure_new_line=True)

		if source:
			self.add_annotation(self.at() - 1, source)

	def dispose_phantoms(self):
		for phantom in self.phantoms:
			phantom.dispose()
		self.phantoms.clear()

	def dispose(self):
		super().dispose()
		self.dispose_phantoms()
		self.protocol.dispose()
