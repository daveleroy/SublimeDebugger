from __future__ import annotations
from dataclasses import dataclass

from .panel import DebuggerProtocolLogger
from .typecheck import *

import sublime

from .import core
from .import dap
from .import ui

from .views import css
from .views.variable import VariableComponent
from .console_view import ConsoleView

if TYPE_CHECKING:
	from .debugger import Debugger

@dataclass
class Group:
	collapsed: bool
	frozen: int # if frozen is > 0 this group cannot be collapsed yet since variables have not been evaluated...
	start: int
	ended: bool

class DebuggerConsole(core.Logger):
	def __init__(self, debugger: Debugger, window: sublime.Window):
		self.on_input: core.Event[str] = core.Event()
		self.on_navigate: core.Event[dap.SourceLocation] = core.Event()

		self.protocol = DebuggerProtocolLogger(window)
		self.window = window
		self.debugger = debugger
		self.panel: ConsoleView|None = None
		self.indent = ''
		self.groups: list[Group] = []

		self.annotation_id = 0

	def dispose(self):
		self.protocol.dispose()
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
		self.protocol.clear()
		self.indent = ''
		self.groups.clear()
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
		group = None

		if self.groups:
			group = self.groups[-1]

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
						self.append_variable(self.debugger, variable, event.source, event.line, at, i, indent)

					if group:
						self.collapse_if_needed(panel, group)

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


			if event.group == 'end':
				group = self.groups.pop()
				region = panel.view.get_regions(f'{id(group)}')[0]
				panel.view.add_regions(f'{id(group)}', [sublime.Region(region.a, at)])
				group.ended = True
				self.collapse_if_needed(panel, group)

			if event.output:
				self.append_text(event.category or 'console', self.indent + event.output, event.source, event.line)

			if event.group == 'start' or event.group == 'startCollapsed':
				self.indent += '\t'
				group = Group(event.group == 'startCollapsed', 0, at, False)
				self.groups.append(group)
				at = panel.at() - 1
				panel.view.add_regions(f'{id(group)}', [sublime.Region(at, at)])


	def collapse_if_needed(self, panel: ConsoleView, group: Group):
		region = panel.view.get_regions(f'{id(group)}')[0]

		if group.collapsed:
			panel.view.fold(sublime.Region(region.a, region.b - 1))



	def append_variable(self, debugger: Debugger, variable: dap.Variable, source: Optional[dap.Source], line: int|None, at: int, index: int, indent: str):
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
			component = VariableComponent(debugger, variable, children_only=True)
			component.set_expanded()
			popup = ui.Popup(panel.view, phantom_at)[
				component
			]


		def edit(edit: sublime.Edit):
			panel.view.set_read_only(False)
			panel.view.insert(edit, at, indent + (variable.value or variable.name or '{variable}'))
			
		core.edit(panel.view, edit)

		phantom = ui.RawPhantom(panel.view, sublime.Region(phantom_at, phantom_at), html, on_navigate)
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
			'important': 'magenta',
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

	def log(self, type: str, value: Any):
		if type == 'transport':
			self.protocol.log('transport', value)
		elif type == 'error':
			panel = self.acquire_panel()
			panel.write(str(value) + '\n', 'red')
		else:
			panel = self.acquire_panel()
			panel.write(str(value) + '\n', 'blue')
