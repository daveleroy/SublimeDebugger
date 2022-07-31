from __future__ import annotations
from typing import TYPE_CHECKING, Any

import sublime

from .import core
from .import ui
from .import dap

from .views.variable import VariableComponent

from .settings import Settings
from .ansi import ansi_colorize

from .debugger_protocol_panel import DebuggerProtocolPanel
from .debugger_output_panel import DebuggerOutputPanel, DebuggerConsoleTabs

if TYPE_CHECKING:
	from .debugger import Debugger



class DebuggerConsoleOutputPanel(DebuggerOutputPanel, core.Logger):
	def __init__(self, debugger: Debugger) -> None:
		super().__init__(debugger, 'Debugger Console', show_tabs=True)

		self.on_input: core.Event[str] = core.Event()
		self.on_navigate: core.Event[dap.SourceLocation] = core.Event()
		self.debugger = debugger

		self.protocol = DebuggerProtocolPanel(debugger)

		self.view.assign_syntax('Packages/Debugger/Commands/DebuggerConsole.sublime-syntax')
		self.color: str|None = None
		self.phantoms = []

		settings = self.view.settings()
		settings.set('line_numbers', False)
		settings.set('gutter', False)
		settings.set('font_size', Settings.ui_scale)
		settings.set('draw_unicode_white_space', 'none')
		settings.set('fade_fold_buttons', False)
		settings.set('scroll_past_end', False)
		
		# settings.set('margin', 0)
		# settings.set('line_padding_top', 0)

		settings.set('context_menu', 'DebuggerWidget.sublime-menu')
		settings.set('auto_complete_selector', 'debugger.console')
		settings.set('debugger.console', True)

		def edit(edit):
			self.view.replace(edit, sublime.Region(0, self.view.size()), '\n' * 25)

		core.edit(self.view, edit)
		self.open()

	def program_output(self, session: dap.Session, event: dap.OutputEvent):
		type = event.category or 'console'
		if type == 'telemetry':
			return


		color_for_type: dict[str|None, str|None] = {
			'stderr': 'red',
			'stdout': 'foreground',
			'debugger.error': 'red',
			'debugger.info': 'blue',
		}

		if event.variablesReference:
			self.write(f' \n', color_for_type.get(type), ensure_new_line=True)
			placeholder = self.add_annotation(self.at() - 1, event.source, event.line)

			async def appendVariabble(variablesReference: int) -> None:
				try:
					variables = await session.get_variables(variablesReference, without_names=True)
					at = placeholder()
					for variable in variables:
						self.write_variable(variable, at)

				# if a request is cancelled it is because the debugger session ended
				# In some cases the variable cannot be fetched since the debugger session was terminated because of the exception
				# However the exception message is actually important and needs to be shown to the user...
				except core.CancelledError:
					print('Unable to fetch variables: Cancelled')
					# todo: this should be inserted into the place the phantom was going to be
					# self.append_text(event.category or 'console', self.indent + event.output, event.source, event.line)

			core.run(appendVariabble(event.variablesReference))

		elif event.output:
			self.write(event.output, color_for_type.get(type))
			if event.source:
				self.add_annotation(self.at() - 1, event.source, event.line)


	def at(self):
		return self.view.size()

	# def ensure_new_line(self, text: str, at: int|None = None):
	# 	if at is None:
	# 		at = self.at()

	# 	if at != 0 and self.view.substr(at -1) != '\n':
	# 		text = '\n' + text

	# 	return text

	def write(self, text: str, color: str|None, ensure_new_line=False):
		# if we are changing color we want it on its own line
		if ensure_new_line or self.color != color:
			text = self.ensure_new_line(text)

		def edit(edit):
			# self.view.set_read_only(False)
			self.view.insert(edit, self.view.size(), ansi_colorize(text, color, self.color))
			# self.view.set_read_only(True)
			self.color = color

		core.edit(self.view, edit)

	def write_variable(self, variable: dap.Variable, at: int):
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
			component = VariableComponent(self.debugger, variable, children_only=True)
			component.set_expanded()
			popup = ui.Popup(self.view, at)[
				component
			]

		def edit(edit: sublime.Edit):
			# self.view.set_read_only(False)
			self.view.insert(edit, at, (variable.value or variable.name or '{variable}'))
			# self.view.set_read_only(True)
			
		core.edit(self.view, edit)

		phantom = ui.RawPhantom(self.view, sublime.Region(at, at), html, on_navigate=on_navigate)
		self.phantoms.append(phantom)

	def add_annotation(self, at: int, source: dap.Source|None, line: int|None):
		if source:
			location = dap.SourceLocation(source, line)
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

			self.view.add_regions(f'an{at}', [sublime.Region(at, at)], annotation_color="#fff0", annotations=[html], on_navigate=on_navigate)
		else:
			self.view.add_regions(f'an{at}', [sublime.Region(at, at)])

		return lambda: self.view.get_regions(f'an{at}')[0].a

	def clear(self):
		self.protocol.clear()
		self.dispose_phantoms()
		def edit(edit):
			# self.view.set_read_only(False)
			self.view.replace(edit, sublime.Region(0, self.view.size()), '\n' * 25)
			# self.view.set_read_only(True)
		core.edit(self.view, edit)
		
	def log(self, type: str, value: Any):
		if type == 'transport':
			self.protocol.log(type, value)
		elif type == 'error':
			self.write(str(value), 'red', ensure_new_line=True)
			self.open()
		elif type == 'stderr':
			self.write(str(value), 'red')
		elif type == 'stdout':
			self.write(str(value), None)
		elif type == 'warn':
			self.write(str(value), 'yellow', ensure_new_line=True)
		else:
			self.write(str(value), 'comment', ensure_new_line=True)

	def dispose_phantoms(self):
		for phantom in self.phantoms:
			phantom.dispose()
		self.phantoms.clear()

	def dispose(self):
		super().dispose()
		self.dispose_phantoms()
		self.protocol.dispose()
