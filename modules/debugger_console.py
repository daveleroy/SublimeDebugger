from __future__ import annotations
from .typecheck import *

import sublime

from .import core
from .import dap
from .import ui

from .views import css
from .views.variable import VariableComponent
from .console_view import ConsoleView


class DebuggerConsole:
	def __init__(self, window: sublime.Window):
		self.on_input: core.Event[str] = core.Event()
		self.on_navigate: core.Event[dap.SourceLocation] = core.Event()

		self.window = window
		self.panel: ConsoleView|None = None
		self.indent = ''

		self.annotation_id = 0

	def dispose(self):
		if self.panel:
			self.panel.dispose()

	def acquire_panel(self) -> ConsoleView:
		if not self.panel or self.panel.is_closed:
			if self.panel:
				self.panel.dispose()
			self.panel = ConsoleView(self.window, 'Debugger Console')
			self.panel.on_input = self.on_input
			self.panel.on_escape.add(self.dispose)

		return self.panel

	def show(self):
		panel = self.acquire_panel()
		self.window.focus_view(panel.view)

	def close(self):
		if self.panel:
			self.panel.close()
			
	def clear(self):
		self.indent = ''
		if self.panel:
			self.panel.clear()

	def program_output(self, session: dap.Session, event: dap.OutputEvent):

		type = event.category or 'console'
		if type == 'telemetry':
			return

		sequences_for_types: dict[str|None, str] = {
			'debugger.error': 'red',
			'stderr': 'red',
			'debugger.info': 'blue',
		}

		type = sequences_for_types.get(type)
		panel = self.acquire_panel()
		variablesReference = event.variablesReference
		if variablesReference:
			# save a place for these phantoms to be written to since we have to evaluate them first
			# panel.write(self.indent)
			placeholder = panel.write_phantom_placeholder(type)
			indent = self.indent

			# this seems to be what vscode does it ignores the actual message here.
			# Some of the messages are junk like 'output' that we probably don't want to display
			async def appendVariabble() -> None:
				try:
					assert variablesReference
					variables = await session.get_variables(variablesReference, without_names=True)

					at = placeholder()
					for i, variable in enumerate(variables):
						self.append_variable(variable, event.source, event.line, at, i, indent)


				# if a request is cancelled it is because the debugger session ended
				# In some cases the variable cannot be fetched since the debugger session was terminated because of the exception
				# However the exception message is actually important and needs to be shown to the user...
				except core.CancelledError:
					print('Unable to fetch variables: Cancelled')
					# todo: this should be inserted into the place the phantom was going to be
					self.append_text(event.category or 'console', self.indent + event.output, event.source, event.line)

			core.run(appendVariabble())
		else:
			at = panel.at()

			if event.group == 'end':
				self.indent = self.indent[:-1]

			self.append_text(event.category or 'console', self.indent + event.output, event.source, event.line)

			if event.group == 'start' or event.group == 'startCollapsed':
				self.indent += '\t'

	def append_variable(self, variable: dap.Variable, source: Optional[dap.Source], line: int|None, at: int, index: int, indent: str):
		panel = self.acquire_panel()
		name = ui.html_escape(f'❯')
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
				<a href="">{name}</a>
			</body>
		'''

		phantom_at = at + len(indent)

		def on_navigate(path: str):
			component = VariableComponent(variable, children_only=True)
			component.set_expanded()
			popup = ui.Popup(panel.view, phantom_at)[
				component
			]


		def edit(edit: sublime.Edit):
			panel.view.set_read_only(False)
			panel.view.insert(edit, at, indent + (variable.value or variable.name or '{variable}'))
			
		core.edit(panel.view, edit)

		phantom = RawPhantom(panel.view, sublime.Region(phantom_at, phantom_at), html, on_navigate)
		panel.phantoms.append(phantom)

		if source:
			self.append_source(at, source, line)


	def append_text(self, type: str|None, text: str, source: Optional[dap.Source], line: int|None):
		if type == 'telemetry':
			return

		sequences_for_types: dict[str|None, str] = {
			'debugger.error': 'red',
			'stderr': 'red',
			'debugger.info': 'blue',
		}

		type = sequences_for_types.get(type)

		panel = self.acquire_panel()

		panel.write(text, type)

		if source:
			self.append_source(None, source, line)

	def append_source(self, at: int|None, source: dap.Source, line: int|None):
		location = dap.SourceLocation(source, line)
		panel = self.acquire_panel()
		at = at or (panel.at() - 1)

		name = ui.html_escape(f'@{location.name}')
		html = f'''
			<style>
			html {{
				background-color: var(--background);
			}}
			a {{
				color: color(var(--foreground) alpha(0.25));
				text-decoration: none;
			}}
			</style>
			<body id="debugger">
				<a href="">{name}</a>
			</body>
		'''
	
		def on_navigate(path: str):
			self.on_navigate(location)

		self.annotation_id += 1
		panel.view.add_regions(f'an{self.annotation_id}', [sublime.Region(at, at)], annotation_color="#fff0", annotations=[html], on_navigate=on_navigate)


	def log_error(self, text: str) -> None:
		panel = self.acquire_panel()
		panel.write(text + '\n', 'red')

	def log_info(self, text: str) -> None:
		panel = self.acquire_panel()
		panel.write(text + '\n', 'blue')


class RawPhantom:	
	def __init__(self, view: sublime.View, region: sublime.Region, html: str, on_navigate: Callable[[str], Any]) -> None:
		self.region = region
		self.view = view
		self.pid = self.view.add_phantom(f'{id(self)}', region, html, sublime.LAYOUT_INLINE, on_navigate)

	def dispose(self) -> None:
		self.view.erase_phantom_by_id(self.pid)