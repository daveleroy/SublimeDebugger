from __future__ import annotations
from typing import TYPE_CHECKING, Any

import sublime

from .import core
from .debugger_output_panel import DebuggerOutputPanel

if TYPE_CHECKING:
	from .debugger import Debugger

class DebuggerProtocolPanel(core.Logger):
	def __init__(self, debugger: Debugger):
		self.debugger = debugger
		self.output: DebuggerOutputPanel|None = None
		self.pending: list[Any] = []

	def write_pending(self):
		if not self.output:
			self.output = DebuggerOutputPanel(self.debugger, 'Debugger Protocol', True)
			self.output.on_opened = lambda: self.write_pending_if_needed()
			self.output.view.assign_syntax('Packages/Debugger/Commands/DebuggerProtocol.sublime-syntax')
			settings = self.output.view.settings()
			settings.set('word_wrap', False)
			settings.set('scroll_past_end', False)

		text = ''
		for pending in self.pending:
			text += f'{pending}\n'

		self.pending.clear()

		self.output.view.run_command('append', {
			'characters': text,
			'force': True,
			'scroll_to_end': True,
		})

	def write_pending_if_needed(self):
		if self.output and self.output.is_open():
			self.write_pending()

	def log(self, type: str, value: Any):
		self.pending.append(value)
		self.write_pending_if_needed()

	def error(self, value: str):
		self.pending.append(f'error: {value}')
		self.write_pending_if_needed()

	def open(self):
		self.write_pending()
		if self.output:
			self.output.open()

	def clear(self):
		self.pending.clear()
		if self.output:
			self.output.dispose()
			self.output = None

	def dispose(self):
		if self.output:
			self.output.dispose()