from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable


if TYPE_CHECKING:
	from .debugger import Debugger

import sublime

from . import core
from . import ui
from . import dap

from .settings import Settings
from .views.variable import VariableView

from .ansi import ansi_colorize

from .protocol import ProtocolWindow
from .output_panel import OutputPanel


class ConsoleOutputPanel(OutputPanel, dap.Console):
	def __init__(self, debugger: Debugger) -> None:
		super().__init__(debugger, 'Debugger', name='Console', show_tabs=True, remove_last_newline=True)

		self.on_input = core.Event[str]()
		self.on_navigate = core.Event[dap.SourceLocation]()
		self.debugger = debugger

		self.protocol = ProtocolWindow()
		self.dispose_add(self.protocol)

		self.view.assign_syntax(core.package_path_relative('contributes/Syntax/DebuggerConsole.sublime-syntax'))
		self.color: str | None = None
		self.phantoms: list[ui.Phantom | ui.RawPhantom | RegionAnnotation] = []
		self.input_size = 0

		self.indent = ''
		self.forced_indent = ''

		self._history_offset = 0
		self._history = []

		self._last_output_event: dap.OutputEvent | None = None

		settings = self.view.settings()
		settings.set('auto_complete_selector', 'debugger.console')

		self.clear()

	def edit(self, fn: Callable[[sublime.Edit], Any]):
		h = self.view.viewport_extent()[1]
		extend_y = self.view.layout_extent()[1]
		position_y = self.view.viewport_position()[1]

		at_bottom_ish = ((position_y + h) - extend_y) >= 0

		is_read_only = self.view.is_read_only()
		if is_read_only:
			self.view.set_read_only(False)
			core.edit(self.view, fn)
			self.view.set_read_only(True)
		else:
			core.edit(self.view, fn)

		if at_bottom_ish:
			self.scroll_to_end()

	def ensure_scrollback_size(self):
		while len(self.phantoms) > Settings.console_scrollback_annotation_limit:
			self.phantoms.pop().dispose()

		line_count = self.view.rowcol(self.view.size())[0]

		if line_count > Settings.console_scrollback_limit:
			remove = 1000 - Settings.console_scrollback_limit
			region = sublime.Region(0, self.view.text_point(remove, 0))
			self.edit(lambda e: self.view.replace(e, region, ''))

	def program_output(self, session: dap.Session, event: dap.OutputEvent):
		type = event.category or 'console'
		if type == 'telemetry':
			return

		source = None
		if event.source:
			source = dap.SourceLocation(event.source, event.line)

		# ignore if the group has the same header
		# this is mostly a workaround for this bug in node... https://github.com/nodejs/node/issues/31973
		if self._last_output_event and self._last_output_event.group == 'start' and self._last_output_event.output == event.output:
			self._last_output_event = event
			return

		self._last_output_event = event

		color_for_type: dict[str | None, str | None] = {
			'stderr': 'red',
			'stdout': 'foreground',
			'important': 'magenta',
		}

		color = color_for_type.get(type) or 'blue'

		if event.group == 'end':
			self.end_indent()

		if event.variablesReference:
			output = event.output
			region = self.write(output, color, ensure_new_line=False, ignore_indent=False, annotation_region=True)

			async def appendVariabble(variablesReference: int) -> None:
				try:
					variables = await session.get_variables(variablesReference, without_names=True)
					at = region.location().a

					for variable in variables:
						self.write_variable(variable, at)

				# if a request is cancelled it is because the debugger session ended
				except core.CancelledError:
					...
				# In some cases the variable cannot be fetched since the debugger session was terminated because of the exception
				# However the exception message is actually important and needs to be shown to the user...
				except Exception:
					core.exception('Unable to fetch variables')
					# todo: this should be inserted into the place the phantom was going to be?
					# self.append_text(event.category or 'console', self.indent + event.output, event.source, event.line)

			core.run(appendVariabble(event.variablesReference))

		elif event.output:
			self.write(event.output, color, ignore_indent=False)
			if event.source:
				RegionAnnotation(self.view, sublime.Region(self.at() - 1), self.on_navigate, source=source)

		if event.group == 'start' or event.group == 'startCollapsed':
			self.start_indent()

	def is_output_identical(self, last_event: dap.OutputEvent, event: dap.OutputEvent):
		if not event.output:
			return False
		return last_event.category == event.category and last_event.output == event.output

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

	def at(self):
		# there is always a single invisible character at the end of the content otherwise every single write causes the phantom to be out of position and require re-rendering
		if input := self.input_region():
			return max(input.a - 1, 0)
		return max(self.view.size() - 1, 0)

	def is_newline_required(self, at: int | None = None):
		if at is None:
			at = self.at()

		if self.removed_newline == at:
			return False

		if at != 0 and self.view.substr(at - 1) != '\n':
			return True

		return False

	def write(self, text: str, color: str | None, ensure_new_line=False, ignore_indent: bool = True, annotation_region: bool = False) -> RegionAnnotation:
		indent = ''

		if not ignore_indent and self.indent:
			indent += self.indent
		if self.forced_indent:
			indent += self.forced_indent

		if indent:
			text = indent + text
			text = text.replace('\n', '\n' + indent, text.count('\n') - 1)

		# if we are changing color we want it on its own line
		if (ensure_new_line or self.color != color) and self.is_newline_required():
			self.edit(lambda edit: self.view.insert(edit, self.at(), '\n'))

		colored = ansi_colorize(text, color, self.color)
		region: Any = None

		def edit(edit: sublime.Edit):
			nonlocal region
			at = self.at()
			self.view.insert(edit, at, colored)
			if annotation_region:
				region = RegionAnnotation(self.view, sublime.Region(at), self.on_navigate)

		self.edit(edit)
		self.color = color

		self.ensure_scrollback_size()
		return region

	def write_variable(self, variable: dap.Variable, at: int):
		html = """
			<style>
			html {
				background-color: var(--background);
			}
			a {
				color: color(var(--foreground) alpha(0.25));
				text-decoration: none;
				padding-left: 0.0rem;
				padding-right: 0.0rem;
			}
			</style>
			<body id="debugger">
				<a href="">❯</a>
			</body>
		"""

		phantom = None

		def on_navigate(_: str):
			nonlocal phantom
			if phantom:
				phantom.dispose()
				phantom = None
				return

			with ui.Phantom(self.view, at, sublime.LAYOUT_BELOW) as p:
				phantom = p
				self.phantoms.append(p)
				with ui.panel():
					view = VariableView(self.debugger, variable, children_only=True)
					view.set_expanded()

		raw_phantom = ui.RawPhantom(self.view, sublime.Region(at, at), html, on_navigate=on_navigate)
		self.phantoms.append(raw_phantom)

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
		input = self.input_region()
		if not input:
			self.view.set_read_only(True)
			return

		sel = self.view.sel()
		end_of_input = input.b

		for region in sel:
			if region.a < end_of_input:
				self.view.set_read_only(True)
				return

			self.view.set_read_only(False)

	# if you type outside of the input region we want it to scroll_to_end so you are tying into the input region
	def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool | None:
		if input := self.input_region():
			sel = self.view.sel()
			end_of_input = input.b

			for region in sel:
				if region.a < end_of_input:
					self.scroll_to_end()
					return

			return
		return None

	def on_post_text_command(self, command_name: str, args: Any):
		if command_name == 'copy':
			sublime.set_clipboard(sublime.get_clipboard().replace('\u200c', '').replace('\u200b', ''))

		# left_delete seems to cause issues with the layout not being updated so manually call on_text_changed
		if command_name == 'left_delete':
			self.force_invalidate_layout()

	def on_text_command(self, command_name: str, args: Any):  # type: ignore
		if not self.view.is_auto_complete_visible() and command_name == 'move' and args['by'] == 'lines':
			self.enable_input_mode()
			if args['forward']:
				self.autofill(-1)
			else:
				self.autofill(1)
			return 'noop'

	def on_query_completions(self, prefix: str, locations: list[int]) -> Any:
		input = self.input_region()
		if not input:
			return

		text = self.view.substr(sublime.Region(input.b, self.view.size()))
		col = locations[0] - input.b
		completions = sublime.CompletionList()

		items: list[sublime.CompletionItem] = []

		for fill in self._history:
			items.append(
				sublime.CompletionItem.command_completion(
					trigger=fill,
					annotation='',
					kind=sublime.KIND_SNIPPET,
					command='insert',
					args={'characters': fill},
				)
			)

		@core.run
		async def fetch():
			try:
				if not self.debugger.session or not self.debugger.session.capabilities.supportsCompletionsRequest:
					raise core.CancelledError

				for completion in await self.debugger.session.completions(text, col):
					if completion.type == 'method':
						kind = sublime.KIND_FUNCTION
					elif completion.type == 'function':
						kind = sublime.KIND_FUNCTION
					elif completion.type == 'constructor':
						kind = sublime.KIND_FUNCTION
					elif completion.type == 'field':
						kind = sublime.KIND_VARIABLE
					elif completion.type == 'variable':
						kind = sublime.KIND_VARIABLE
					elif completion.type == 'class':
						kind = sublime.KIND_TYPE
					elif completion.type == 'interface':
						kind = sublime.KIND_TYPE
					elif completion.type == 'module':
						kind = sublime.KIND_NAMESPACE
					elif completion.type == 'property':
						kind = sublime.KIND_VARIABLE
					elif completion.type == 'enum':
						kind = sublime.KIND_TYPE
					elif completion.type == 'keyword':
						kind = sublime.KIND_KEYWORD
					elif completion.type == 'snippet':
						kind = sublime.KIND_SNIPPET
					else:
						kind = sublime.KIND_VARIABLE

					item = sublime.CompletionItem.command_completion(
						trigger=completion.text or completion.label,
						annotation=completion.detail or '',
						kind=kind,
						command='insert',
						args={'characters': completion.text or completion.label},
					)

					items.append(item)

			except core.Error as e:
				core.debug('Unable to fetch completions:', e)

			except core.CancelledError:
				...

			completions.set_completions(items, sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_REORDER | sublime.INHIBIT_WORD_COMPLETIONS)

		fetch()
		return completions

	def on_deactivated(self):
		if input := self.input_region():
			text_region = sublime.Region(input.b, self.view.size())
			if text_region.size() == 0:
				self.disable_input_mode()

	def input_region(self):
		regions = self.view.get_regions('input')
		if not regions:
			return None
		region = regions[0]

		if region.size() != self.input_size:
			self.view.erase_regions('input')
			self.edit(lambda edit: self.view.erase(edit, region))
			return None

		return region

	def disable_input_mode(self):
		if input := self.input_region():
			self.view.erase_regions('input')
			self.edit(lambda edit: self.view.erase(edit, sublime.Region(input.a, self.view.size())))

	def enable_input_mode(self):
		if self.input_region():
			return

		size = self.view.size()

		def edit(edit):
			marker = '\n\u200c:' if size > 1 else '\u200c:'
			input_size = self.view.insert(edit, size, marker)
			self.input_size = input_size
			self.view.add_regions('input', [sublime.Region(size, size + input_size)])

		self.edit(edit)
		self.view.set_read_only(False)
		self.scroll_to_end()

	def enter(self):
		input = self.input_region()
		if not input:
			self.enable_input_mode()
			return False

		text_region = sublime.Region(input.b, self.view.size())
		text = self.view.substr(text_region)
		if not text:
			self.disable_input_mode()
			return True

		self.edit(
			lambda edit: (
				self.view.erase(edit, text_region),
				self.view.sel().clear(),
				self.view.sel().add(self.view.size()),
			)
		)

		self.on_input(text)
		self.write(':' + text, 'comment', True)
		self._history_offset = 0
		self._history.append(text)

		# reset the input mode since line 0 is handled differntly in enable_input_mode and we just added a newline
		self.disable_input_mode()
		self.enable_input_mode()
		return True

	def autofill(self, offset: int):
		self._history_offset += offset
		self._history_offset = min(max(0, self._history_offset), len(self._history))
		self.enable_input_mode()
		input = self.input_region()
		if not input:
			return False

		text_region = sublime.Region(input.b, self.view.size())
		if self._history_offset:
			self.edit(
				lambda edit: (
					self.view.replace(edit, text_region, self._history[-self._history_offset]),
					self.view.sel().clear(),
					self.view.sel().add(self.view.size()),
				)
			)
		else:
			self.edit(
				lambda edit: (
					self.view.erase(edit, text_region),
					self.view.sel().clear(),
					self.view.sel().add(self.view.size()),
				)
			)

	def log(self, type: str, value: Any, source: dap.SourceLocation | None = None, session: dap.Session | None = None, phantom: ui.Html | None = None):
		if type == 'transport':
			self.protocol.log('transport', value, session)
		elif type == 'error-no-open':
			self.write(str(value).rstrip('\n'), 'red', ensure_new_line=True)
		elif type == 'error':
			self.write(str(value).rstrip('\n'), 'red', ensure_new_line=True)
			self.open()
		elif type == 'group-start':
			if value is not None:
				self.write(str(value), None, ensure_new_line=True)
			self.start_indent(forced=True)
		elif type == 'group-end':
			self.end_indent(forced=True)
			if value is not None:
				self.write(str(value), None, ensure_new_line=True)
		elif type == 'stdout':
			self.protocol.log('stdout', value, session)
			self.write(str(value), None)
		elif type == 'stderr':
			self.protocol.log('stderr', value, session)
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
			self.phantoms.append(RegionAnnotation(self.view, sublime.Region(self.at() - 1), self.on_navigate, source=source))

		if phantom:
			self.phantoms.append(ui.RawPhantom(self.view, self.at() - 1, html=phantom.html, on_navigate=phantom.on_navigate))

	def dispose_phantoms(self):
		for phantom in self.phantoms:
			phantom.dispose()
		self.phantoms.clear()

	def dispose(self):
		super().dispose()
		self.dispose_phantoms()
		self.protocol.dispose()


class RegionAnnotation(core.Dispose):
	next_annotation_id = 0

	def __init__(self, view: sublime.View, region: sublime.Region, on_navigate: Callable[[dap.SourceLocation], Any], count: int | None = None, source: dap.SourceLocation | None = None) -> None:
		self.view = view

		RegionAnnotation.next_annotation_id += 1
		self.id = f'debugger.{RegionAnnotation.next_annotation_id}'

		self.on_navigate = on_navigate
		self._update(region, count, source)

		self.dispose_add(lambda: self.view.erase_regions(self.id))

	def update(self, count: int | None, source: dap.SourceLocation | None):
		self._update(self.location(), count, source)

	def _update(self, region: sublime.Region, count: int | None, source: dap.SourceLocation | None):
		if source or count and count > 1:
			if source:
				on_navigate = lambda _: self.on_navigate(source)
				source_html = f'<a href="">{source.name}</a>'
			else:
				on_navigate = None
				source_html = ''

			count_html = f'<span>{count}</span>' if count else ''

			html = f"""
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
			"""

			self.view.add_regions(self.id, [region], annotation_color='#fff0', annotations=[html], on_navigate=on_navigate)
		else:
			self.view.add_regions(self.id, [region])

	def location(self):
		return self.view.get_regions(self.id)[0]
