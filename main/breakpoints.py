
from debug.core.typecheck import Tuple, List, Optional, Any

import sublime
from debug import ui, core

class Filter:
	def __init__(self, id: str, name: str, enabled: bool) -> None:
		self.id = id
		self.name = name
		self.enabled = enabled

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
	def line(self) -> int:
		return self._line

	@property
	def verified(self):
		if self._result:
			return self._result.verified
		return True

	def into_json (self) -> dict:
		return {
			'file': self.file,
			'line': self.line,
			'enabled': self.enabled,
			'condition': self.condition,
			'log': self.log,
			'count' : self.count
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

	def update_views(self) -> None:
		views = self.views
		self.clear_views()
		for view in views:
			self.add_to_view(view)

	def add_to_view(self, view: sublime.View) -> None:
		self.views.append(view)
		p = view.text_point(self.line - 1, 0)
		image = self.image().file
		view.add_regions(self.regionName, [sublime.Region(p, p)], scope ='type', icon=image, flags=sublime.HIDDEN)

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
		self.filters = [] #type: List[Filter]

		self.onMovedBreakpoints = core.Event() #type: core.Event[Tuple[()]]
		self.onChangedBreakpoint = core.Event() #type: core.Event[Breakpoint]
		self.onResultBreakpoint = core.Event() #type: core.Event[Breakpoint]
		self.onRemovedBreakpoint = core.Event() #type: core.Event[Breakpoint]
		self.onAddedBreakpoint = core.Event() #type: core.Event[Breakpoint]

		self.onChangedFilter = core.Event() #type: core.Event[Filter]

		self.onSelectedBreakpoint = core.Event() #type: core.Event[Optional[Breakpoint]]
		self.selected_breakpoint = None #type: Optional[Breakpoint]

		def update_views(breakpoint: Breakpoint) -> None:
			breakpoint.update_views()

		self.onChangedBreakpoint.add(update_views)
		self.onResultBreakpoint.add(update_views)
		
		self.disposeables = [
			ui.view_gutter_double_clicked.add(self.on_gutter_double_clicked),
			ui.view_activated.add(self.on_view_activated),
			ui.view_modified.add(self.view_modified)
		] #type: List[Any]

	
	def clear_breakpoint(self) -> None:
		self.selected_breakpoint = None
		self.onSelectedBreakpoint.post(None)
		
	def select_breakpoint(self, breakpoint: Breakpoint) -> None:
		self.selected_breakpoint = breakpoint
		self.onSelectedBreakpoint.post(breakpoint)
		
	def toggle_filter(self, filter: Filter) -> None:
		filter.enabled = not filter.enabled
		self.onChangedFilter.post(filter)
	def add_filter(self, id: str, name: str, initial: bool) -> None:
		for filter in self.filters:
			if filter.id == id:
				return
		self.filters.append(Filter(id, name, initial))

	def dispose(self) -> None:
		for d in self.disposeables:
			d.dispose()

		for bp in self.breakpoints:
			bp.clear_views()
	def view_modified(self, view: sublime.View):
		self.sync(view) 
	def on_view_activated(self, view: sublime.View):
		self.sync_from_breakpoints(view) 
	def on_gutter_double_clicked(self, event: ui.GutterEvent) -> None:
		print('toggle: breakpoint {}'.format(event))
		self.toggle(event.view, event.line + 1)
		 		
	def remove_breakpoint(self, b: Breakpoint) -> None:
		b.clear_views()
		self.breakpoints.remove(b)
		self.onChangedBreakpoint.post(b)
		self.onRemovedBreakpoint.post(b)

	def breakpoints_for_file(self, file: str) -> List[Breakpoint]:
		r = []
		for b in self.breakpoints:
			if b.file == file:
				r.append (b)
		return r

	def get_breakpoint(self, file: str, line: int) -> Optional[Breakpoint]:
		for b in self.breakpoints:
			if b.file != file:
				continue
			if b.line == line:
				return b
		return None

	def add(self, breakpoint: Breakpoint):
		self.breakpoints.append(breakpoint)
		self.breakpoints.sort()
		self.onChangedBreakpoint.post(breakpoint)
		self.onAddedBreakpoint.post(breakpoint)
		view = sublime.active_window().active_view()
		if view:
			self.sync_from_breakpoints(view) 

	def add_breakpoint(self, file: str, line: int):
		b = Breakpoint(file, line, True)
		self.add(b)

	def toggle_enabled(self, breakpoint: Breakpoint) -> None:
		breakpoint._enabled = not breakpoint.enabled
		self.onChangedBreakpoint.post(breakpoint)

	def set_breakpoint_log(self, breakpoint: Breakpoint, log: Optional[str]) -> None:
		breakpoint._log = log
		self.onChangedBreakpoint.post(breakpoint)

	def set_breakpoint_condition(self, breakpoint: Breakpoint, condition: Optional[str]) -> None:
		breakpoint._condition = condition
		self.onChangedBreakpoint.post(breakpoint)

	def set_breakpoint_count(self, breakpoint: Breakpoint, count: Optional[str]) -> None:
		breakpoint._count = count
		self.onChangedBreakpoint.post(breakpoint)

	def set_breakpoint_result(self, breakpoint: Breakpoint, result: BreakpointResult) -> None:
		breakpoint._result = result
		self.onResultBreakpoint.post(breakpoint)

	def clear_breakpoint_results(self) -> None:
		for breakpoint in self.breakpoints:
			breakpoint._result = None
			self.onResultBreakpoint.post(breakpoint)

	def add_breakpoint_to_view(self, view: sublime.View, b: Breakpoint) -> None:
		b.add_to_view(view)

	# changes the data model to match up with the view regions
	# adds any breakpoints found in the data model that are not found on the view
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
		if dirty:
			self.onMovedBreakpoints.post(())

	# moves the view regions to match up with the data model
	def sync_from_breakpoints(self, view: sublime.View) -> None:
		for b in self.breakpoints:
			view.erase_regions(b.regionName)

		self.sync(view)

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

			#FIXME this only removes from the view it was clicked on from
			# it could be visible in multiple views...
			view.erase_regions(identifier)
			self.remove_breakpoint(b)
			return
		#add the breakpoint
		self.add_breakpoint(file, line)
		self.sync(view)
