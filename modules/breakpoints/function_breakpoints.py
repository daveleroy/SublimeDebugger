from __future__ import annotations
from typing import Any

from ..import core
from ..import ui
from ..import dap

from .breakpoint import Breakpoint


class FunctionBreakpoint(Breakpoint):
	def __init__(self, breakpoint: dap.FunctionBreakpoint, enabled: bool = True):
		super().__init__()
		self.enabled = enabled
		self.dap = breakpoint

	def into_json(self) -> core.JSON:
		return core.JSON({
			'dap': self.dap,
			'enabled': self.enabled
		})

	@staticmethod
	def from_json(json: core.JSON):
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
	def condition(self):
		return self.dap.condition

	@property
	def hitCondition(self):
		return self.dap.hitCondition


class FunctionBreakpoints:
	def __init__(self):
		self.breakpoints: list[FunctionBreakpoint] = []
		self.on_updated = core.Event['list[FunctionBreakpoint]']()
		self.on_send = core.Event['list[FunctionBreakpoint]']()

	def __iter__(self):
		return iter(self.breakpoints)

	def into_json(self) -> list[Any]:
		return list(map(lambda b: b.into_json(), self.breakpoints))

	def load_json(self, json: list[Any]):
		self.breakpoints = list(map(lambda j: FunctionBreakpoint.from_json(j), json))
		self.on_updated(self.breakpoints)

	def set_breakpoint_result(self, breakpoint: FunctionBreakpoint, session: dap.Session, result: dap.Breakpoint):
		breakpoint.set_breakpoint_result(session, result)
		self.updated(send=False)

	def clear_breakpoint_result(self, session: dap.Session):
		for breakpoint in self.breakpoints:
			breakpoint.clear_breakpoint_result(session)

		self.updated(send=False)

	def updated(self, send: bool = True):
		self.on_updated(self.breakpoints)
		if send:
			self.on_send(self.breakpoints)

	def toggle_enabled(self, breakpoint: FunctionBreakpoint):
		breakpoint.enabled = not breakpoint.enabled
		self.updated()

	def edit(self, breakpoint: FunctionBreakpoint, index = 4):
		def set_name(value: str):
			if value:
				breakpoint.dap.name = value
				self.updated()
			self.edit(breakpoint, index=0).run()

		def set_condition(value: str):
			breakpoint.dap.condition = value or None
			self.updated()
			self.edit(breakpoint, index=1).run()

		def set_hit_condition(value: str):
			breakpoint.dap.hitCondition = value or None
			self.updated()
			self.edit(breakpoint, index=2).run()

		def toggle_enabled():
			self.toggle_enabled(breakpoint)
			self.edit(breakpoint, index=3).run()

		def remove():
			self.remove(breakpoint)

		return ui.InputList('Edit Breakpoint on function {}'.format(breakpoint.name), index=index)[
			ui.InputListItemCheckedText(
				set_name,
				'Function',
				'Name of function to break on',
				breakpoint.dap.name,
			),
			ui.InputListItemCheckedText(
				set_condition,
				'Condition',
				'Breaks when expression is true',
				breakpoint.dap.condition,
			),
			ui.InputListItemCheckedText(
				set_hit_condition,
				'Count',
				'Breaks when hit count condition is met',
				breakpoint.dap.hitCondition,
			),
			ui.InputListItemChecked(
				toggle_enabled,
				breakpoint.enabled,
				'Enabled',
				'Disabled',
			),
			ui.InputListItem(
				remove,
				'Remove'
			),
		]

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

	def remove(self, breakpoint: FunctionBreakpoint):
		self.breakpoints.remove(breakpoint)
		self.updated()

	def remove_all(self):
		self.breakpoints = []
		self.updated()
