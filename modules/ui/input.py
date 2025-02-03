from __future__ import annotations
from typing import Any, Callable, Protocol, Sequence

from ..import core

import sublime
import sublime_plugin

from dataclasses import dataclass

class CommandPaletteInputCommand:
	running_command: CommandPaletteInputCommand|None = None

	def __init__(self, window: sublime.Window, input: InputList|InputText):
		self.window = window
		self.input = input
		self.future: core.Future[None] = core.Future()

		def _on_cancel():
			CommandPaletteInputCommand.running_command = None
			if not self.future.done():
				self.future.set_result(None)

		def _on_run_internal():
			self.future.set_result(None)

		input._on_cancel_internal = _on_cancel #type: ignore
		input._on_run_internal = _on_run_internal #type: ignore

		# if you don't clear the text then the debugger_input command can't be found in the command pallete....
		self.window.run_command('show_overlay', {
			'overlay': 'command_palette',
			'text': '',
		})

		self.hide_overlay()
		CommandPaletteInputCommand.running_command = self
		self.window.run_command('show_overlay', {
			'overlay': 'command_palette',
			'command': 'debugger_input',
		})
		CommandPaletteInputCommand.running_command = self

	async def wait(self):
		await self.future


	def hide_overlay(self):
		self.window.run_command('hide_overlay', {
			'overlay': 'command_palette',
		})

	@staticmethod
	def cancel_running_command():
		if CommandPaletteInputCommand.running_command:
			CommandPaletteInputCommand.running_command.hide_overlay()

@dataclass
class InputListItem:
	run: Callable[[], Any] | InputList | InputText
	text: str
	name: str | None = None # name of this input when nested
	annotation: str = ''
	details: list[str]|str = ''
	kind: tuple[int, str, str] = sublime.KIND_AMBIGUOUS

	run_alt: Callable[[], Any] | InputList | InputText| None = None
	preview: Callable[[], str|sublime.Html|None]|None = None

	def display_or_run(self):
		if callable(self.run):
			self.run()
		else:
			self.run.run()

class InputList(sublime_plugin.ListInputHandler):
	id = 0

	def __init__(self, placeholder: str = '', index: int = 0):
		super().__init__()
		self._next_input = None
		self.values: Sequence[InputListItem] = []
		self._placeholder = placeholder
		self.index = index

		self._on_cancel_internal: Callable[[], None] | None = None
		self._on_run_internal: Callable[[], None] | None = None

		self.arg_name = 'list_{}'.format(InputList.id)
		InputList.id += 1

	def __getitem__(self, values: Sequence[InputListItem]|InputListItem):
		self.values = values if isinstance(values, Sequence) else [values]
		return self

	def __await__(self):
		return self.run().__await__()

	@core.run
	async def run(self):
		command = CommandPaletteInputCommand(sublime.active_window(), self)
		try:
			await command.wait()
		except core.CancelledError as e:
			command.hide_overlay()

	def name(self):
		return self.arg_name

	def placeholder(self):
		return self._placeholder

	def want_event(self) -> bool:
		return True

	def list_items(self): #type: ignore
		items: list[sublime.ListInputItem] = []
		for index, value in enumerate(self.values):
			items.append(sublime.ListInputItem(value.text, index, details=value.details, kind=value.kind, annotation=value.annotation)) #type: ignore

		if (not items):
			return ['Nothing Here\terror?']

		return (items, self.index)

	def confirm(self, arg: int, event:Any=None):
		modifier_keys = event.get('modifier_keys', {})
		is_alt = modifier_keys.get('super') or modifier_keys.get('alt')

		if is_alt:
			run = self.values[arg].run_alt

		else:
			run = self.values[arg].run

		if callable(run):
			run()
		else:
			self._next_input = run

		if self._on_run_internal:
			self._on_run_internal()

	def preview(self, arg: int): #type: ignore
		if preview := self.values[arg].preview:
			return preview()

	def next_input(self, args: Any): #type: ignore
		n = self._next_input
		self._next_input = None
		return n

	def validate(self, value: int, event: Any): #type: ignore
		return True

	def cancel(self):
		if self._on_cancel_internal:
			self._on_cancel_internal()

	def description(self, value: int, text: str): #type: ignore
		return self.values[value].name or self.values[value].text.split('\t')[0]

class InputEnable (Protocol):
	def enable(self):
		...
	def disable(self):
		...

class InputText(sublime_plugin.TextInputHandler):
	id = 0

	def __init__(self, run: Callable[[str], Any] | InputList | InputText, placeholder: str|None = None, initial: str|None = None, enable_when_active: InputEnable|None = None):
		super().__init__()
		self._placeholder = placeholder
		self._initial = initial
		self._run = run

		self._next_input = None

		self._on_cancel_internal: Callable[[], None] | None = None
		self._on_run_internal: Callable[[], None] | None = None

		self._enable = enable_when_active
		self.arg_name = 'text_{}'.format(InputText.id)
		InputText.id += 1

	@core.run
	async def run(self):
		await CommandPaletteInputCommand(sublime.active_window(), self).wait()

	def __await__(self):
		return self.run().__await__()

	def placeholder(self): #type: ignore
		if self._enable:
			self._enable.enable()
		return self._placeholder

	def initial_text(self): #type: ignore
		return self._initial

	def confirm(self, arg: str, event: Any = None):
		if callable(self._run):
			self._run(arg)
		else:
			self._next_input = self._run

		if self._on_run_internal:
			self._on_run_internal()

	def next_input(self, args: Any): #type: ignore
		n = self._next_input
		self._next_input = None
		return n

	def name(self):
		return self.arg_name

	def cancel(self):
		if self._enable:
			self._enable.disable()
		if self._on_cancel_internal:
			self._on_cancel_internal()

def InputListItemCheckedText(run: Callable[[str], Any] | InputList | InputText, name: str, description: str, value: str|None):
	if value:
		kind = (sublime.KIND_ID_AMBIGUOUS, core.platform.unicode_checked_sigil, '')
		input_name = name
		annotation = value
	else:
		kind = (sublime.KIND_ID_AMBIGUOUS, core.platform.unicode_unchecked_sigil, '')
		input_name = name
		annotation = description

	return InputListItem(
		InputText(
			run,
			description,
			value
		),
		input_name,
		name,
		annotation=annotation,
		kind=kind
	)

def InputListItemOnOff(run: Callable[[], Any] | InputList | InputText, true: str, false: str, value: bool):
	if value:
		return InputListItem(run, true, annotation='On')
	else:
		return InputListItem(run, false, annotation='Off')

def InputListItemChecked(run: Callable[[], Any] | InputList | InputText, value: bool, true: str, false: str|None = None, details: list[str]|str = '', run_alt: Callable[[], Any] | InputList | InputText|None = None):
	if value:
		kind = (sublime.KIND_ID_AMBIGUOUS, core.platform.unicode_checked_sigil, 'On')
		text = true
	else:
		kind = (sublime.KIND_ID_AMBIGUOUS, core.platform.unicode_unchecked_sigil, 'Off')
		text = false or true

	return InputListItem(
		run,
		text,
		kind=kind,
		details=details,
		run_alt=run_alt,
	)
