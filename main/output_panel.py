
from sublime_db.core.typecheck import (
	Callable,
	Optional,
	Dict,
	List,
	Any
)

import sublime
import sublime_plugin

from sublime_db import core
from sublime_db import ui

from .debugger import CompletionItem

_phantom_text = " \n\n\n\n\n\n\n"


class CommandPrompComponent (ui.Component):
	def __init__(self, text: str) -> None:
		super().__init__()
		self.text = text

	def render(self) -> ui.components:
		return [
			ui.Label(self.text),
			ui.Img(ui.Images.shared.right)
		]


class PanelInputHandler (ui.InputHandler):
	def __init__(self, panel: 'OutputPhantomsPanel', label: str, text: str, on_change: Callable[[str], None], on_done: Callable[[Optional[str]], None]) -> None:
		self.on_done = on_done
		self.on_change = on_change
		self.label = label
		self.text = text
		self.panel = panel
		self.panel.run_input_handler(self)

	def close(self) -> None:
		self.panel.clear_input_handler(self, None)


class OutputPhantomsPanel:
	panels = {} #type: Dict[int, OutputPhantomsPanel]

	@staticmethod
	def for_view(view: sublime.View) -> 'Optional[OutputPhantomsPanel]':
		return OutputPhantomsPanel.panels.get(view.id())

	def __init__(self, window: sublime.Window, name: str) -> None:
		self.header_text = ""
		self.name = name
		self.window = window

		self.view = window.create_output_panel(name)
		self.show()

		# we need enough space to place our phantoms in increasing regions (1, 1), (1, 2)... etc
		# otherwise they will get reordered when one of them gets redrawn
		# we use new lines so we don't have extra space on the rhs
		self.view.run_command('debug_output_phantoms_panel_setup')
		settings = self.view.settings()

		# cover up the addition space we added during the insert
		# the additional space is so we can have an input bar at the top of the debugger
		# removes some additional padding on the top of the view
		settings.set("margin", 0)
		settings.set('line_padding_top', -9)
		settings.set('gutter', False)
		settings.set('word_wrap', False)

		self.view.sel().clear()

		self.input_handler = None #type: Optional[PanelInputHandler]
		self.promptPhantom = None #type: Optional[ui.Phantom]
		OutputPhantomsPanel.panels[self.view.id()] = self

	def isHidden(self) -> bool:
		return self.window.active_panel() != 'output.{}'.format(self.name)

	def show(self) -> None:
		self.window.run_command('show_panel', {
			'panel': 'output.{}'.format(self.name)
		})

	def hide(self) -> None:
		if self.window.active_panel() != self.name:
			return

		self.window.run_command('hide_panel', {
			'panel': 'output.{}'.format(self.name)
		})

	def phantom_location(self) -> int:
		return self.view.size() - len(_phantom_text) + 2

	def dispose(self) -> None:
		self.window.destroy_output_panel(self.name)
		del OutputPhantomsPanel.panels[self.view.id()]

	def run_input_handler(self, input_handler: PanelInputHandler) -> None:
		self.input_handler = input_handler
		self.header_text = '  '
		self.view.run_command('debug_output_phantoms_panel_reset', {
			'header': self.header_text,
			'characters': input_handler.text,
		})
		self.view.settings().set('line_padding_top', 0)
		self.view.sel().clear()
		self.view.sel().add(self.editable_region())

		if self.promptPhantom:
			self.promptPhantom.dispose()
		self.promptPhantom = ui.Phantom(CommandPrompComponent(input_handler.label), self.view, sublime.Region(1, 1))

	def clear_input_handler(self, input_handler: PanelInputHandler, text: Optional[str]) -> None:
		if not self.input_handler:
			return
		if self.input_handler != input_handler:
			return

		if self.promptPhantom:
			self.promptPhantom.dispose()
			self.promptPhantom = None

		self.header_text = ''
		self.view.run_command('debug_output_phantoms_panel_reset', {
			'header': '',
			'characters': '',
		})

		self.view.settings().set('line_padding_top', -9)
		self.input_handler.on_done(text)
		self.input_handler = None

	def editable_region(self) -> sublime.Region:
		min_point = len(self.header_text)
		max_point = self.view.size() - len(_phantom_text) + 1
		return sublime.Region(min_point, max_point)

	def close_input(self) -> None:
		if self.input_handler:
			self.clear_input_handler(self.input_handler, None)

	def on_updated_input(self, text: str) -> None:
		if self.input_handler:
			self.input_handler.on_change(text)

	def on_done_input(self, text: str) -> None:
		print('on_done_input')
		if not self.input_handler:
			return
		self.clear_input_handler(self.input_handler, text)


class DebugNullCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		pass


class DebugOutputPhantomsPanelSetupCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		self.view.insert(edit, 0, _phantom_text)


class DebugSetContentsCommand(sublime_plugin.TextCommand):
	def run(self, edit, characters):
		self.view.erase(edit, sublime.Region(0, self.view.size()))
		self.view.insert(edit, 0, characters)

class DebugOutputPhantomsPanelResetCommand(sublime_plugin.TextCommand):
	def run(self, edit, header, characters):
		region = sublime.Region(0, self.view.size() - len(_phantom_text) + 1)
		self.view.erase(edit, region)
		self.view.insert(edit, 0, header + characters)


class DebugOutputPhantomsPanelEventListener(sublime_plugin.EventListener):
	def __init__(self) -> None:
		super().__init__()
		self.completions = [] #type: List[CompletionItem]
		self.getting_completions_text = "."
		self.used_completions = False
		self.ignore_next_modification = False

	@core.async
	def get_completions(self, view: sublime.View, text: str) -> core.awaitable[None]:
		from sublime_db.main.main import Main

		window = view.window()
		m = Main.forWindow(window)
		if m:
			adapter = m.debugger.adapter
		if not adapter:
			return
		self.completions = yield from adapter.Completions(text, len(text) + 1, m.debugger.frame)
		view.run_command("hide_auto_complete")
		view.run_command("auto_complete", {
                    'disable_auto_insert': True,
                    'next_completion_if_showing': False
                })

	def on_query_completions(self, view, prefix, locations) -> Any:
		panel = OutputPhantomsPanel.for_view(view)
		if not panel:
			return

		text = self.editable_text(panel)
		if text != self.getting_completions_text:
			self.getting_completions_text = text
			core.run(self.get_completions(view, text))

		items = []
		for completion in self.completions:
			items.append([completion.label, completion.text or completion.label])
		return items

	def on_modified(self, view: sublime.View) -> None:
		if self.ignore_next_modification:
			self.ignore_next_modification = False
			return

		panel = OutputPhantomsPanel.for_view(view)
		if not panel:
			return

		text = self.editable_text(panel)
		core.main_loop.call_soon_threadsafe(panel.on_updated_input, text)
		if text and text != self.getting_completions_text:
			self.getting_completions_text = text
			core.run(self.get_completions(view, text))

	def editable_text(self, panel: OutputPhantomsPanel) -> str:
		return panel.view.substr(self.editable_region(panel)).strip()

	def editable_region(self, panel: OutputPhantomsPanel) -> sublime.Region:
		min_point = len(panel.header_text)
		max_point = panel.view.size() - len(_phantom_text) + 1
		return sublime.Region(min_point, max_point)

	def can_left_delete(self, panel: OutputPhantomsPanel) -> bool:
		edit_region = self.editable_region(panel)
		for region in panel.view.sel():
			if region.a < edit_region.a or region.b <= edit_region.a:
				return False
		return True

	def can_right_delete(self, panel: OutputPhantomsPanel) -> bool:
		edit_region = self.editable_region(panel)
		for region in panel.view.sel():
			if region.a >= edit_region.b or region.b >= edit_region.b:
				return False
		return True

	def on_text_command(self, view, command_name: str, args) -> Any:
		panel = OutputPhantomsPanel.for_view(view)
		if not panel:
			return

		if command_name == "commit_completion":
			self.ignore_next_modification = True
			return None

		if command_name == "left_delete":
			if self.can_left_delete(panel):
				return None
			else:
				return ("debug_null", {})

		if command_name == "right_delete":
			if self.can_right_delete(panel):
				return None
			else:
				return ("debug_null", {})

		if command_name == 'insert' and args['characters'] == '\n':
			text = self.editable_text(panel)
			core.main_loop.call_soon_threadsafe(panel.on_done_input, text)
			return ("debug_null", {})

	def on_selection_modified(self, view: sublime.View) -> None:
		panel = OutputPhantomsPanel.for_view(view)
		if not panel:
			return

		sel = panel.view.sel()

		valid_region = panel.editable_region()
		regions = []
		for i in range(0, len(sel)):
			region = sel[i]
			if region.a < valid_region.a:
				region.a = valid_region.a
			if region.a > valid_region.b:
				region.a = valid_region.b

			if region.b < valid_region.a:
				region.b = valid_region.a
			if region.b > valid_region.b:
				region.b = valid_region.b
			regions.append(region)

		sel.clear()
		sel.add_all(regions)
