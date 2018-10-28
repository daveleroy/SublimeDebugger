
from sublime_db import ui

from sublime_db.main.breakpoints import Breakpoints, Breakpoint

class BreakpointInlineComponent (ui.Component):
	def __init__(self, breakpoints: Breakpoints, breakpoint: Breakpoint) -> None:
		super().__init__()
		self.breakpoints = breakpoints
		self.breakpoint = breakpoint

	def on_remove(self) -> None:
		self.breakpoints.remove_breakpoint(self.breakpoint)
		
	def on_enter_expression(self, value: str) -> bool:
		print('Enter: ', value)
		self.breakpoints.set_breakpoint_condition(self.breakpoint, value)
		return True

	def on_enter_log(self, value: str) -> bool:
		self.breakpoints.set_breakpoint_log(self.breakpoint, value)
		return True

	def on_enter_count(self, value: str) -> bool:
		self.breakpoints.set_breakpoint_count(self.breakpoint, value)
		return True

	def render (self) -> ui.components:
		count =  self.breakpoint.count or ''
		condition = self.breakpoint.condition or ''
		log =  self.breakpoint.log or ''
		return [
			ui.Table(table_items = [
				ui.TableItem(items = [
					ui.Box(items = [
						ui.Label('expr', width = 6),
					]),
					ui.Input(on_done = self.on_enter_expression, hint = 'Breaks when expression is true', text = condition, width = 50),
				]),
				ui.TableItem(items = [
					ui.Box(items = [
						ui.Label('log', width = 6),
					]),
					ui.Input(on_done = self.on_enter_log, hint = 'Message to log, expressions within {} are interpolated', text = log, width = 50),
				]),
				ui.TableItem(items = [
					ui.Box(items = [
						ui.Label('count', width = 6),
					]),
					ui.Input(on_done = self.on_enter_count, hint = 'Break when hit count condition is met', text = count, width = 50),
				]),
				ui.TableItem(items = [
					ui.Box(items = [
						ui.Button(self.on_remove, items = [
							ui.Label('Remove', width = 6),
						]),
					]),
				]),
			])
		]
