from __future__ import annotations
from ..typecheck import *

from ..import core
from ..import ui
from ..import dap

class FunctionBreakpoint:
	def __init__(self, breakpoint: dap.FunctionBreakpoint, enabled: bool = True):
		self.enabled = enabled
		self.dap = breakpoint
		self.result: dap.Breakpoint | None = None

	def into_json(self) -> dap.Json:
		return {
			'dap': self.dap,
			'enabled': self.enabled
		}

	@staticmethod
	def from_json(json: dap.Json):
		return FunctionBreakpoint(
			json['dap'],
			json['enabled']
		)

	@property
	def image(self):
		if not self.enabled:
			return ui.Images.shared.dot_disabled
		if not self.verified:
			return ui.Images.shared.dot_emtpy

		return ui.Images.shared.dot

	@property
	def tag(self):
		return 'ƒn'

	@property
	def name(self):
		return self.dap.name

	@property
	def description(self) -> str|None:
		if self.result:
			return self.result.message
		return None

	@property
	def condition(self):
		return self.dap.condition

	@property
	def hitCondition(self):
		return self.dap.hitCondition

	@property
	def verified(self):
		if self.result:
			return self.result.verified
		return True

class FunctionBreakpoints:
	def __init__(self):
		self.breakpoints: list[FunctionBreakpoint] = []
		self.on_updated: core.Event[list[FunctionBreakpoint]] = core.Event()
		self.on_send: core.Event[list[FunctionBreakpoint]] = core.Event()

	def __iter__(self):
		return iter(self.breakpoints)

	def into_json(self) -> list[Any]:
		return list(map(lambda b: b.into_json(), self.breakpoints))

	def load_json(self, json: list[Any]):
		self.breakpoints = list(map(lambda j: FunctionBreakpoint.from_json(j), json))
		self.on_updated(self.breakpoints)

	def clear_session_data(self):
		for breakpoint in self.breakpoints:
			breakpoint.result = None
		self.updated(send=False)

	def updated(self, send: bool = True):
		self.on_updated(self.breakpoints)
		if send:
			self.on_send(self.breakpoints)

	def set_result(self, breakpoint: FunctionBreakpoint, result: dap.Breakpoint):
		breakpoint.result = result
		self.updated(send=False)

	def toggle_enabled(self, breakpoint: FunctionBreakpoint):
		breakpoint.enabled = not breakpoint.enabled
		self.updated()

	def edit(self, breakpoint: FunctionBreakpoint):
		def set_name(value: str):
			if value:
				breakpoint.dap.name = value
				self.updated()

		def set_condition(value: str):
			breakpoint.dap.condition = value or None
			self.updated()

		def set_hit_condition(value: str):
			breakpoint.dap.hitCondition = value or None
			self.updated()

		def toggle_enabled():
			self.toggle_enabled(breakpoint)

		def remove():
			self.breakpoints.remove(breakpoint)
			self.updated()

		return ui.InputList([
			ui.InputListItemCheckedText(
				set_name,
				"Function",
				"Name of function to break on",
				breakpoint.dap.name,
			),
			ui.InputListItemCheckedText(
				set_condition,
				"Condition",
				"Breaks when expression is true",
				breakpoint.dap.condition,
			),
			ui.InputListItemCheckedText(
				set_hit_condition,
				"Count",
				"Breaks when hit count condition is met",
				breakpoint.dap.hitCondition,
			),
			ui.InputListItemChecked(
				toggle_enabled,
				breakpoint.enabled,
				"Enabled",
				"Disabled",
			),
			ui.InputListItem(
				remove,
				"Remove"
			),
		], placeholder="Edit Breakpoint on function {}".format(breakpoint.name))

	def add_command(self):
		ui.InputText(self.add, "Name of function to break on").run()

	def add(self, name: str):
		self.breakpoints.append(
			FunctionBreakpoint(
				dap.FunctionBreakpoint(name, None, None),
				enabled=True
			)
		)
		self.updated()

	def remove_all(self):
		self.breakpoints = []
		self.updated()
