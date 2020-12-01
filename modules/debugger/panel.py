import sublime
from ..import core
from .settings import Settings

class OutputPanel:
	def __init__(self, window: sublime.Window, name: str, show_panel: bool = True):
		self.output_name = name
		self.window = window
		self.output_name = f'Debugger: {self.output_name}'

		# if a panel with the same name already exists add a unique id
		if f'output.{self.output_name}' in self.window.panels():
			self.output_name += f'({id(self)})'

		previous_panel = self.window.active_panel()
		self.view = self.window.create_output_panel(self.output_name)

		if not show_panel and previous_panel:
			self.window.run_command('show_panel', {
				'panel': previous_panel
			})

	def dispose(self):
		print(f'OutputPanel: dispose {self.output_name}')
		self.window.destroy_output_panel(self.output_name)

	def open(self):
		self.window.run_command('show_panel', {
			'panel': f'output.{self.output_name}'
		})

	def clear(self):
		view = self.view
		core.edit(view, lambda edit: view.erase(edit, sublime.Region(0, view.size())))

	def write(self, text: str):
		self.view.run_command('append', {
			'characters': text,
			'force': True,
			'scroll_to_end': True
		})


class DebuggerProtocolLogger(core.Logger):
	def __init__(self, window: sublime.Window):
		self.window = window
		self.panel = OutputPanel(window, 'Protocol', show_panel=False)
		self.panel.view.assign_syntax('Packages/Debugger/Commands/LogPanel.sublime-syntax')
		settings = self.panel.view.settings()
		settings.set('word_wrap', False)

	def info(self, message: str):
		self.panel.write(f'{message}\n')

	def error(self, message: str):
		self.panel.write(f'error: {message}\n')

	def clear(self):
		self.panel.clear()

	def dispose(self):
		self.panel.dispose()

_phantom_text = "\u200F\u200F\u200F\u200F\u200F"

class DebuggerOutputPanel:
	def __init__(self, window: sublime.Window):
		super().__init__()

		self.window = window

		self.panel = self.window.create_output_panel("Debugger")
		self.panel_show()
		# we need enough space to place our phantoms in increasing regions (1, 1), (1, 2)... etc
		# otherwise they will get reordered when one of them gets redrawn
		# we use zero width characters so we don't have extra around phantoms
		self.panel.run_command('insert', {
			'characters': _phantom_text
		})

		settings = self.panel.settings()
		settings.set("margin", 0)
		settings.set('line_padding_top', 3)
		settings.set('gutter', False)
		settings.set('word_wrap', True)
		settings.set('line_spacing', 0)
		settings.set('context_menu', 'Widget Debug.sublime-menu')
		settings.set('draw_centered', True)
		settings.set('is_widget', True)
		settings.set('sublime_debugger', True)
		settings.set("font_face", Settings.font_face)
		self.panel.sel().clear()

		def on_hide_panel(window: sublime.Window):
			name = window.active_panel() or ''

			# show main debugger panel after closing other debugger panels
			if window == self.window and name != 'output.Debugger' and name.startswith('output.Debugger:'):
				core.log_info(f'Showing debug panel')
				self.panel_show()
				return True

			if Settings.hide_status_bar:
				self.window.set_status_bar_visible(True)

			return False

		def on_show_panel(window: sublime.Window):
			name = window.active_panel()
			if Settings.hide_status_bar:
				if name != 'output.Debugger':
					self.window.set_status_bar_visible(True)
				else:
					self.window.set_status_bar_visible(False)

		core.on_pre_hide_panel.add(on_hide_panel)
		core.on_post_show_panel.add(on_show_panel)

	def dispose(self):
		self.window.destroy_output_panel("Debugger")

	def is_panel_visible(self) -> bool:
		return self.window.active_panel() == "output.Debugger"


	def set_ui_scale(self, ui_scale: float):
		self.panel.settings().set('font_size', ui_scale)

	def panel_show(self) -> None:
		self.window.run_command('show_panel', {
			'panel': 'output.{}'.format("Debugger")
		})

	def panel_hide(self) -> None:
		if self.window.active_panel() != "Debugger":
			return

		self.window.run_command('hide_panel', {
			'panel': 'output.{}'.format("Debugger")
		})

	def panel_phantom_location(self) -> int:
		return self.panel.size() - len(_phantom_text) + 2

	def panel_phantom_view(self) -> sublime.View:
		return self.panel

