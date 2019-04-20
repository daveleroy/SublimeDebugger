
from sublime_db.core.typecheck import Tuple, List, Optional, Any

import sublime
from sublime_db import ui, core


class FunctionBreakpoint:
	def __init__(self, name: str, condition: Optional[str] = None, hitCondition: Optional[str] = None, enabled: bool = True) -> None:
		self._name = name
		self._enabled = enabled
		self._condition = condition
		self._hitCondition = hitCondition

	def into_json(self) -> dict:
		return {
			'name': self.name,
			'condition': self.condition,
			'hitCondition': self.hitCondition,
			'enabled': self.enabled
		}

	@staticmethod
	def from_json(json: dict) -> 'FunctionBreakpoint':
		return FunctionBreakpoint(json['name'], json['condition'], json['hitCondition'], json['enabled'])

	def image(self) -> ui.Image:
		if not self.enabled:
			return ui.Images.shared.dot_disabled
		if not self.verified:
			return ui.Images.shared.dot_emtpy

		return ui.Images.shared.dot
	
	@property
	def enabled(self):
		return self._enabled

	@property
	def name(self):
		return self._name

	@property
	def condition(self):
		return self._condition

	@property
	def hitCondition(self):
		return self._hitCondition

	@property
	def verified(self):
		return True

class Filter:
	def __init__(self, id: str, name: str, enabled: bool) -> None:
		self.id = id
		self.name = name
		self.enabled = enabled

	def into_json(self) -> dict:
		return {
			'id': self.id,
			'name': self.name,
			'enabled': self.enabled
		}

	@staticmethod
	def from_json(json: dict) -> 'Filter':
		return Filter(json['id'], json['name'], json['enabled'])


# additonal information about this breakpoint from the debug adapter
class BreakpointResult:
	def __init__(self, verified: bool, line: int, message: Optional[str]) -> None:
		self.verified = verified
		self.line = line
		self.message = message


# note: Breakpoint lines are 1 based
class Breakpoint:
	_next_id = 0

	def __init__(self, file: str, line: int, enabled: bool) -> None:
		self.id = Breakpoint._next_id
		Breakpoint._next_id += 1

		self.regionName = 'bp{}'.format(self.id)
		self._file = file
		self._line = line
		self._enabled = enabled
		self._condition = None #type: Optional[str]
		self._log = None #type: Optional[str]
		self._count = None #type: Optional[str]
		self.views = [] #type: List[sublime.View]
		self._result = None #type: Optional[BreakpointResult]

	@property
	def file(self): 
		return self._file

	@property
	def line(self) -> int:
		return self._line

	@property
	def enabled(self):
		return self._enabled

	@property
	def condition(self):
		return self._condition

	@property
	def log(self):
		return self._log

	@property
	def count(self):
		return self._count

	@property
	def verified(self):
		if self._result:
			return self._result.verified
		return True

	def into_json(self) -> dict:
		return {
			'file': self.file,
			'line': self.line,
			'enabled': self.enabled,
			'condition': self.condition,
			'log': self.log,
			'count': self.count
		}

	@staticmethod
	def from_json(json: dict) -> 'Breakpoint':
		file = json['file']
		line = json['line']
		enabled = json['enabled']
		breakpoint = Breakpoint(file, line, enabled)
		breakpoint._condition = json['condition']
		breakpoint._log = json['log']
		breakpoint._count = json['count']
		return breakpoint

	def image(self) -> ui.Image:
		if not self.enabled:
			return ui.Images.shared.dot_disabled
		if not self.verified:
			return ui.Images.shared.dot_emtpy
		if self.log:
			return ui.Images.shared.dot_log
		if self.condition or self.count:
			return ui.Images.shared.dot_expr
		return ui.Images.shared.dot

	def scope(self) -> str:
		if not self.enabled:
			return 'markup.ignored.debug'
		if not self.verified:
			return 'markup.ignored.debug'
		return 'markup.deleted.debug'

	def update_views(self) -> None:
		for view in self.views:
			self.refresh_view(view)

	def refresh_view(self, view: sublime.View) -> None:
		regions = view.get_regions(self.regionName)
		p = view.text_point(self.line - 1, 0)
		view.erase_regions(self.regionName)
		view.add_regions(self.regionName, [sublime.Region(p, p)], scope=self.scope(), icon=self.image().file, flags=sublime.HIDDEN)

	def add_to_view(self, view: sublime.View) -> None:
		for old_view in self.views:
			if old_view.id == view.id:
				self.refresh_view(view)
				return

		self.views.append(view)
		self.refresh_view(view)

	def clear_views(self) -> None:
		for view in self.views:
			view.erase_regions(self.regionName)
		self.views = []

	def __lt__(self, other: 'Breakpoint'):
		if self.file.__lt__(other.file):
			return True
		return self.line.__lt__(other.line)


class Breakpoints:
	def __init__(self) -> None:
		self.breakpoints = [] #type: List[Breakpoint]
		self.functionBreakpoints = [] #type: List[FunctionBreakpoint]
		self.filters = [] #type: List[Filter]

		self.onSendFunctionBreakpointToDebugger = core.Event() #type: core.Event[FunctionBreakpoint]
		# send when added, removed, updated (but not moved)
		self.onSendBreakpointToDebugger = core.Event() #type: core.Event[Breakpoint]

		self.onUpdatedFunctionBreakpoint = core.Event() #type: core.Event[FunctionBreakpoint]
		self.onUpdatedBreakpoint = core.Event() #type: core.Event[Breakpoint]

		self.onChangedBreakpoint = core.Event() #type: core.Event[Breakpoint]

		self.onUpdatedFilter = core.Event() #type: core.Event[Filter]
		self.onSendFilterToDebugger = self.onUpdatedFilter

		self.onSelectedBreakpoint = core.Event() #type: core.Event[Optional[Breakpoint]]
		self.selected_breakpoint = None #type: Optional[Breakpoint]

		def update_views(breakpoint: Breakpoint) -> None:
			breakpoint.update_views()

		self.onUpdatedBreakpoint.add(update_views)

		self.disposeables = [
			ui.view_gutter_double_clicked.add(self.on_gutter_double_clicked),
			ui.view_activated.add(self.on_view_activated),
			ui.view_modified.add(self.view_modified)
		] #type: List[Any]

		self.sync_dirty_scheduled = False
		self.dirty_views = {} #type: Dict[int, sublime.View]

	def load_from_json(self, json) -> None:
		for breakpoint_json in json.get('breakpoints', []):
			bp = Breakpoint.from_json(breakpoint_json)
			self.breakpoints.append(bp)
		for breakpoint_json in json.get('file_breakpoints', []):
			bp = FunctionBreakpoint.from_json(breakpoint_json)
			self.functionBreakpoints.append(bp)

	def into_json(self) -> dict:
		json = {}
		json_breakpoints = []
		for bp in self.breakpoints:
			json_breakpoints.append(bp.into_json())
		json['breakpoints'] = json_breakpoints


		json_file_breakpoints = []
		for bp in self.functionBreakpoints:
			json_file_breakpoints.append(bp.into_json())
		json['file_breakpoints'] = json_file_breakpoints
		return json

	def dispose(self) -> None:
		for d in self.disposeables:
			d.dispose()
		for bp in self.breakpoints:
			bp.clear_views()

	def breakpoint_for_id(self, id):
		for breakpoint in self.breakpoints:
			if breakpoint.id == id:
				return breakpoint

	def toggle_filter(self, filter: Filter) -> None:
		filter.enabled = not filter.enabled
		self.onUpdatedFilter.post(filter)

	def add_filter(self, id: str, name: str, initial: bool) -> None:
		for filter in self.filters:
			if filter.id == id:
				return
		self.filters.append(Filter(id, name, initial))

	def add_function_breakpoint(self, name: str) -> None:
		bp = FunctionBreakpoint(name)
		self.functionBreakpoints.append(bp)
		self.onSendFunctionBreakpointToDebugger.post(bp)
		self.onUpdatedFunctionBreakpoint.post(bp)
	def clear_selected_breakpoint(self) -> None:
		self.selected_breakpoint = None
		self.onSelectedBreakpoint.post(None)

	def clear_all_breakpoints(self):
		while len(self.functionBreakpoints) > 0:
			self.remove_breakpoint(self.functionBreakpoints[-1])
		while len(self.breakpoints) > 0:
			self.remove_breakpoint(self.breakpoints[-1])

	def select_breakpoint(self, breakpoint: Breakpoint) -> None:
		self.selected_breakpoint = breakpoint
		self.onSelectedBreakpoint.post(breakpoint)

	def remove_breakpoint(self, b: Breakpoint) -> None:
		if isinstance(b, Breakpoint):
			b.clear_views()
			self.breakpoints.remove(b)
			self.onSendBreakpointToDebugger.post(b)
			self.onUpdatedBreakpoint.post(b)

		elif isinstance(b, FunctionBreakpoint):
			self.functionBreakpoints.remove(b)
			self.onSendFunctionBreakpointToDebugger.post(b)
			self.onUpdatedFunctionBreakpoint.post(b)
		else:
			assert False, "expected Breakpoint or FunctionBreakpoint"

	def breakpoints_for_file(self, file: str) -> List[Breakpoint]:
		r = []
		for b in self.breakpoints:
			if b.file == file:
				r.append(b)
		return r

	def get_breakpoint(self, file: str, line: int) -> Optional[Breakpoint]:
		for b in self.breakpoints:
			if b.file != file:
				continue
			if b.line == line:
				return b
		return None

	def add_breakpoint(self, file: str, line: int):
		b = Breakpoint(file, line, True)
		self.add(b)

	def add(self, breakpoint: Breakpoint):
		self.breakpoints.append(breakpoint)
		self.breakpoints.sort()
		self.onSendBreakpointToDebugger.post(breakpoint)
		self.onUpdatedBreakpoint.post(breakpoint)
		view = sublime.active_window().active_view()
		if view:
			self.sync_from_breakpoints(view)

	def toggle_enabled(self, breakpoint: Breakpoint) -> None:
		self.set_breakpoint_enabled(breakpoint, not breakpoint.enabled)

	def set_breakpoint_enabled(self, breakpoint: Breakpoint, enabled: bool) -> None:
		if isinstance(breakpoint, Breakpoint):
			breakpoint._enabled = enabled
			self.onSendBreakpointToDebugger.post(breakpoint)
			self.onUpdatedBreakpoint.post(breakpoint)
		elif isinstance(breakpoint, FunctionBreakpoint):
			breakpoint._enabled = enabled
			self.onSendFunctionBreakpointToDebugger.post(breakpoint)
			self.onUpdatedFunctionBreakpoint.post(breakpoint)
		else:
			assert False, "expected Breakpoint or FunctionBreakpoint"

	def set_breakpoint_log(self, breakpoint: Breakpoint, log: Optional[str]) -> None:
		breakpoint._log = log
		self.onSendBreakpointToDebugger.post(breakpoint)
		self.onUpdatedBreakpoint.post(breakpoint)

	def set_breakpoint_condition(self, breakpoint: Breakpoint, condition: Optional[str]) -> None:
		if isinstance(breakpoint, Breakpoint):
			breakpoint._condition = condition
			self.onSendBreakpointToDebugger.post(breakpoint)
			self.onUpdatedBreakpoint.post(breakpoint)
		elif isinstance(breakpoint, FunctionBreakpoint):
			breakpoint._condition = condition
			self.onSendFunctionBreakpointToDebugger.post(breakpoint)
			self.onUpdatedFunctionBreakpoint.post(breakpoint)
		else:
			assert False, "expected Breakpoint or FunctionBreakpoint"

	def set_breakpoint_count(self, breakpoint: Breakpoint, count: Optional[str]) -> None:
		if isinstance(breakpoint, Breakpoint):
			breakpoint._count = count
			self.onSendBreakpointToDebugger.post(breakpoint)
			self.onUpdatedBreakpoint.post(breakpoint)
		elif isinstance(breakpoint, FunctionBreakpoint):
			breakpoint._hitCondition = count
			self.onSendFunctionBreakpointToDebugger.post(breakpoint)
			self.onUpdatedFunctionBreakpoint.post(breakpoint)
		else:
			assert False, "expected Breakpoint or FunctionBreakpoint"

	def set_breakpoint_result(self, breakpoint: Breakpoint, result: BreakpointResult) -> None:
		breakpoint._result = result
		self.onUpdatedBreakpoint.post(breakpoint)

	def clear_breakpoint_results(self) -> None:
		for breakpoint in self.breakpoints:
			breakpoint._result = None
			self.onUpdatedBreakpoint.post(breakpoint)

	def add_breakpoint_to_view(self, view: sublime.View, b: Breakpoint) -> None:
		b.add_to_view(view)

	def view_modified(self, view: sublime.View):
		if view.file_name() is None:
			return

		if not self.sync_dirty_scheduled:
			ui.Timer(self.sync_dirty, 1, False)
			self.sync_dirty_scheduled = True

		self.dirty_views[view.id()] = view

	def on_view_activated(self, view: sublime.View):
		self.sync_from_breakpoints(view)

	def on_gutter_double_clicked(self, event: ui.GutterEvent) -> None:
		print('toggle: breakpoint {}'.format(event))
		self.toggle(event.view, event.line + 1)
	# changes the data model to match up with the view regions
	# adds any breakpoints found in the data model that are not found on the view

	def sync_dirty(self) -> None:
		self.sync_dirty_scheduled = False
		for view in self.dirty_views.values():
			self.sync(view)

	def sync(self, view: sublime.View) -> None:
		file = view.file_name()
		print('Breakpoints: sync view ', file)
		dirty = False
		for b in self.breakpoints:
			if b.file != file:
				continue
			identifier = b.regionName
			regions = view.get_regions(identifier)
			if len(regions) == 0:
				print('Error: Failed to find breakpoint that should be set, re-adding')
				self.add_breakpoint_to_view(view, b)
				dirty = True
			else:
				dirty = True
				line = view.rowcol(regions[0].a)[0] + 1
				if line != b.line:
					dirty = True
					b._line = line
					self.onUpdatedBreakpoint.post(b)			

	# moves the view regions to match up with the data model
	def sync_from_breakpoints(self, view: sublime.View) -> None:
		file = view.file_name()
		for breakpoint in self.breakpoints:
			if breakpoint.file != file:
				continue
			breakpoint.add_to_view(view)

	# FIXME this is OLD code that should be updated...
	def toggle(self, view: sublime.View, line: int) -> None:
		print('Breakpoint: toggle', line)
		self.sync(view)
		file = view.file_name()
		if not file:
			return

		for b in self.breakpoints:
			if b.file != file:
				continue
			if b.line != line:
				continue
			identifier = b.regionName

			# FIXME this only removes from the view it was clicked on from
			# it could be visible in multiple views...
			view.erase_regions(identifier)
			self.remove_breakpoint(b)
			return
		# add the breakpoint
		self.add_breakpoint(file, line)
		self.sync(view)
