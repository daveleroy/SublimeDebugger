from __future__ import annotations
from typing import Any, Literal

from ..import core
from ..import ui
from ..import dap

from .breakpoint import Breakpoint

class DataBreakpoint(Breakpoint):
	def __init__(self, breakpoint: dap.DataBreakpoint, info: dap.DataBreakpointInfoResponse, enabled: bool):
		super().__init__()
		self.dap = breakpoint
		self.info = info
		self.enabled = enabled

	@property
	def image(self) -> ui.Image:
		if not self.enabled:
			return ui.Images.shared.dot_disabled
		if not self.verified:
			return ui.Images.shared.dot_emtpy
		return ui.Images.shared.dot

	@property
	def tag(self) -> str|None:
		return "0x"

	@property
	def name(self) -> str:
		return self.info.description

	def into_json(self) -> dict[str, Any]:
		return {
			'dap': self.dap,
			'info': self.info,
			'enabled': self.enabled,
		}

	@staticmethod
	def from_json(json: dict[str, Any]) -> 'DataBreakpoint':
		return DataBreakpoint(
			json['info'],
			json['data'],
			json['enabled']
		)

class DataBreakpoints:
	def __init__(self):
		self.breakpoints: list[DataBreakpoint] = []
		self.on_updated = core.Event['list[DataBreakpoint]']()
		self.on_send = core.Event['list[DataBreakpoint]']()

	def __iter__(self):
		return iter(self.breakpoints)

	def updated(self, send: bool = True):
		self.on_updated(self.breakpoints)
		if send:
			self.on_send(self.breakpoints)

	def set_breakpoint_result(self, breakpoint: DataBreakpoint, session: dap.Session, result: dap.Breakpoint):
		breakpoint.set_breakpoint_result(session, result)
		self.updated(send=False)

	def clear_breakpoint_result(self, session: dap.Session):
		for breakpoint in self.breakpoints:
			breakpoint.clear_breakpoint_result(session)

		self.breakpoints = list(filter(lambda b: b.info.canPersist, self.breakpoints))
		self.updated(send=False)

	def toggle_enabled(self, breakpoint: DataBreakpoint):
		breakpoint.enabled = not breakpoint.enabled
		self.updated()

	def edit(self, breakpoint: DataBreakpoint, index=3):
		def set_condition(value: str):
			breakpoint.dap.condition = value or None
			self.updated()
			self.edit(breakpoint, index=0).run()

		def set_hit_condition(value: str):
			breakpoint.dap.hitCondition = value or None
			self.updated()
			self.edit(breakpoint, index=1).run()

		def toggle_enabled():
			self.toggle_enabled(breakpoint)
			self.edit(breakpoint, index=2).run()

		def remove():
			self.breakpoints.remove(breakpoint)
			self.updated()

		return ui.InputList('Edit Breakpoint @ {}'.format(breakpoint.name), index=index)[
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
		]

	def add(self, info: dap.DataBreakpointInfoResponse, type: Literal['read','write','readWrite']|None):
		assert info.dataId, "this info request has no id"
		self.breakpoints.append(
			DataBreakpoint(
				dap.DataBreakpoint(info.dataId, type),
				info,
				enabled=True
			)
		)
		self.updated()

	def remove(self, breakpoint: DataBreakpoint):
		self.breakpoints.remove(breakpoint)
		self.updated()

	def remove_unpersistable(self):
		self.breakpoints = list(filter(lambda b: b.info.canPersist, self.breakpoints))
		self.updated()

	def remove_all(self):
		self.breakpoints = []
		self.updated()
