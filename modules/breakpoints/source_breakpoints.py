from __future__ import annotations
from ..typecheck import *

from ..import core
from ..import ui
from ..import dap

import sublime
import os

# note: Breakpoint lines are 1 based (sublime lines are 0 based)
class SourceBreakpoint:
	next_id = 0

	def __init__(self, breakpoints: SourceBreakpoints, file: str, line: int, column: int|None, enabled: bool):
		SourceBreakpoint.next_id += 1
		self.id = SourceBreakpoint.next_id
		self.region_name = 'bp{}'.format(self.id)
		self.views: list[SourceBreakpointView] = []

		self.dap = dap.SourceBreakpoint(line, column, None, None, None)
		self._file = file
		self.enabled = enabled
		self.result: dap.Breakpoint | None = None
		self.breakpoints = breakpoints

	@property
	def tag(self):
		if self.column:
			return '{}:{}'.format(self.line, self.column)
		return str(self.line)

	@property
	def name(self):
		return os.path.basename(self._file)

	@property
	def description(self) -> str|None:
		if self.result:
			return self.result.message
		return None

	@property
	def file(self):
		return self._file

	@property
	def line(self):
		if self.result and self.result.line:
			return self.result.line
		return self.dap.line

	@property
	def column(self):
		if self.result and self.result.column:
			return self.result.column
		return self.dap.column

	@property
	def verified(self):
		if self.result:
			return self.result.verified
		return True

	def into_json(self) -> dap.Json:
		return {
			'file': self.file,
			'line': self.dap.line,
			'column': self.dap.column,
			'enabled': self.enabled,
			'condition': self.dap.condition,
			'logMessage': self.dap.logMessage,
			'hitCondition': self.dap.hitCondition
		}

	@staticmethod
	def from_json(breakoints: SourceBreakpoints, json: dap.Json):
		file = json['file']
		line = json['line']
		column = json.get('column')
		enabled = json['enabled']
		breakpoint = SourceBreakpoint(breakoints, file, line, column, enabled)
		breakpoint.dap.hitCondition = json['condition']
		breakpoint.dap.logMessage = json['logMessage']
		breakpoint.dap.hitCondition = json['hitCondition']
		return breakpoint

	@property
	def image(self):
		if not self.enabled:
			return ui.Images.shared.dot_disabled
		if not self.verified:
			return ui.Images.shared.dot_emtpy
		if self.dap.logMessage:
			return ui.Images.shared.dot_log
		if self.dap.condition or self.dap.hitCondition:
			return ui.Images.shared.dot_expr
		return ui.Images.shared.dot

	def scope(self):
		return 'text'

	def update_views(self):
		for view in self.views:
			view.render()

	def add_to_view(self, view: sublime.View):
		for old_view in self.views:
			if old_view.view.id() == view.id():
				old_view.render()
				return

		def show_edit_menu():
			self.breakpoints.edit(self).run()

		self.views.append(SourceBreakpointView(self, view, show_edit_menu))

	def clear_views(self):
		for view in self.views:
			view.dispose()
		self.views = []

	def __lt__(self, other: SourceBreakpoint):
		return (self.file, self.line, self.column or 0) < (other.file, other.line, other.column or 0)

class SourceBreakpointView:
	def __init__(self, breakpoint: SourceBreakpoint, view: sublime.View, on_click_inline: Callable[[], None]):
		self.breakpoint = breakpoint
		self.view = view
		self.column_phantom: ui.Phantom|None = None
		self.on_click_inline = on_click_inline
		self.render()

	def render(self):
		self.dispose()

		image = self.breakpoint.image
		line = self.breakpoint.line
		column = self.breakpoint.column

		p = self.view.text_point(line - 1, 0)

		self.view.add_regions(self.breakpoint.region_name, [sublime.Region(p, p)], scope=self.breakpoint.scope(), icon=image.file, flags=sublime.HIDDEN)

		if column and self.breakpoint.dap.column:
			p = self.view.text_point(line - 1, column - 1)
			self.column_phantom = ui.Phantom(self.view, sublime.Region(p, p))[
				ui.click(self.on_click_inline)[
					ui.icon(image, height=2, width=2, padding=0)
				]
			]

	def dispose(self):
		self.view.erase_regions(self.breakpoint.region_name)
		if self.column_phantom:
			self.column_phantom.dispose()
			self.column_phantom = None

class SourceBreakpoints:
	def __init__(self):
		self.breakpoints: list[SourceBreakpoint] = []
		self.on_updated: core.Event[SourceBreakpoint] = core.Event()
		self.on_send: core.Event[SourceBreakpoint] = core.Event()

		self.disposeables = [
			core.on_view_activated.add(self.on_view_activated),
			core.on_view_modified.add(self.view_modified)
		]

		self.sync_dirty_scheduled = False
		self.dirty_views: dict[int, sublime.View] = {}

	def __iter__(self):
		return iter(self.breakpoints)

	def into_json(self) -> list[Any]:
		return list(map(lambda b: b.into_json(), self.breakpoints))

	def load_json(self, json: list[Any]):
		self.breakpoints = list(map(lambda j: SourceBreakpoint.from_json(self, j), json))
		self.breakpoints.sort()
		self.add_breakpoints_to_current_view()

	def clear_session_data(self):
		for breakpoint in self.breakpoints:
			if breakpoint.result:
				breakpoint.result = None
				self.updated(breakpoint, send=False)

	def updated(self, breakpoint: SourceBreakpoint, send: bool=True):
		breakpoint.update_views()
		self.on_updated(breakpoint)
		if send:
			self.on_send(breakpoint)

	def dispose(self):
		for d in self.disposeables:
			d.dispose()
		for bp in self.breakpoints:
			bp.clear_views()

	def edit(self, breakpoint: SourceBreakpoint):
		def set_log(value: str):
			breakpoint.dap.logMessage = value or None
			self.updated(breakpoint)

		def set_condition(value: str):
			breakpoint.dap.condition = value or None
			self.updated(breakpoint)

		def set_hit_condition(value: str):
			breakpoint.dap.hitCondition = value or None
			self.updated(breakpoint)

		def toggle_enabled():
			self.toggle_enabled(breakpoint)

		def remove():
			self.remove(breakpoint)

		return ui.InputList([
			ui.InputListItemCheckedText(
				set_log,
				"Log",
				"Message to log, expressions within {} are interpolated",
				breakpoint.dap.logMessage,
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
				"Enabled",
			),
			ui.InputListItem(
				remove,
				"Remove"
			),
		], placeholder="Edit Breakpoint in {} @ {}".format(breakpoint.name, breakpoint.tag))


	def toggle_file_line(self, file: str, line: int):
		bps = self.get_breakpoints_on_line(file, line)
		if bps:
			for bp in bps:
				self.remove(bp)
		else:
			self.add_breakpoint(file, line)

	def edit_breakpoints(self, source_breakpoints: list[SourceBreakpoint]):
		if not source_breakpoints:
			return

		if len(source_breakpoints) == 1:
			self.edit(source_breakpoints[0]).run()
			return

		items: list[ui.InputListItem] = []
		for breakpoint in source_breakpoints:
			items.append(
				ui.InputListItem(
					self.edit(breakpoint),
					"Breakpoint @ {}".format(breakpoint.tag),
				)
			)

		ui.InputList(items).run()

	# todo: fix... this is going to trigger a ton of breakpoint requests if the debugger is active
	def remove_all(self):
		while self.breakpoints:
			self.remove(self.breakpoints[0])

	def remove(self, breakpoint: SourceBreakpoint):
		breakpoint.clear_views()
		self.breakpoints.remove(breakpoint)
		self.updated(breakpoint)

	def toggle_enabled(self, breakpoint: SourceBreakpoint):
		breakpoint.enabled = not breakpoint.enabled
		self.updated(breakpoint)

	def toggle(self, file: str, line: int, column: int|None = None):
		breakpoint = self.get_breakpoint(file, line, column)
		if breakpoint:
			self.remove(breakpoint)
		else:
			self.add_breakpoint(file, line, column)

	def breakpoints_for_file(self, file: str) -> list[SourceBreakpoint]:
		r = list(filter(lambda b: b.file == file, self.breakpoints))
		return r

	def breakpoints_per_file(self) -> dict[str, list[SourceBreakpoint]]:
		bps: dict[str, list[SourceBreakpoint]] = {}
		for breakpoint in self.breakpoints:
			if breakpoint.file in bps:
				bps[breakpoint.file].append(breakpoint)
			else:
				bps[breakpoint.file] = [breakpoint]
		return bps

	def get_breakpoint(self, file: str, line: int, column: int|None = None):
		for b in self.breakpoints:
			if b.file == file and b.line == line and b.column == column:
				return b
		return None

	def get_breakpoints_on_line(self, file: str, line: int) -> list[SourceBreakpoint]:
		r = list(filter(lambda b: b.file == file and b.line == line, self.breakpoints))
		return r

	def add_breakpoint(self, file: str, line: int, column: int|None = None):
		# ensure we don't add a breakpoint that is at the same location
		# note: compare to the uderlying dap module since breakpoint.line/column reflect the actual location of the breakpoint
		# after it has been verified
		for breakpoint in self.breakpoints:
			if breakpoint.file == file and breakpoint.dap.line == line and breakpoint.dap.column == column:
				return

		breakpoint = SourceBreakpoint(self, file, line, column, True)
		self.breakpoints.append(breakpoint)
		self.breakpoints.sort()
		self.updated(breakpoint)
		self.add_breakpoints_to_current_view()
		return breakpoint

	def add_breakpoints_to_current_view(self):
		view = sublime.active_window().active_view()
		if view:
			self.sync_from_breakpoints(view)

	def set_result(self, breakpoint: SourceBreakpoint, result: dap.Breakpoint):
		breakpoint.result = result
		self.updated(breakpoint, send=False)

	def view_modified(self, view: sublime.View):
		if view.file_name() is None:
			return

		if not self.sync_dirty_scheduled:
			core.timer(self.sync_dirty, 1, False)
			self.sync_dirty_scheduled = True

		self.dirty_views[view.id()] = view

	def on_view_activated(self, view: sublime.View):
		self.sync_from_breakpoints(view)

	def sync_dirty(self):
		self.sync_dirty_scheduled = False
		for view in self.dirty_views.values():
			self.sync(view)

	# changes the data model to match up with the view regions
	# adds any breakpoints found in the data model that are not found on the view
	def sync(self, view: sublime.View):
		file = view.file_name()
		if not file:
			return

		dirty = False
		for b in self.breakpoints:
			if b.file != file:
				continue
			identifier = b.region_name
			regions = view.get_regions(identifier)
			if len(regions) == 0:
				b.add_to_view(view)
				dirty = True
			else:
				dirty = True
				line = view.rowcol(regions[0].a)[0] + 1
				if line != b.line:
					dirty = True
					b.dap.line = line
					self.updated(b, send=False)

	# moves the view regions to match up with the data model
	def sync_from_breakpoints(self, view: sublime.View):
		file = view.file_name()
		for breakpoint in self.breakpoints:
			if breakpoint.file != file:
				continue
			breakpoint.add_to_view(view)
