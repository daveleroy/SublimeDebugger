from ..command import ActionElement
from ..views.breakpoints import BreakpointView


class EditBreakpoint(ActionElement):
	name = 'Edit Breakpoint'
	key = 'edit_breakpoint'
	element = BreakpointView

	def action(self, debugger, element: BreakpointView):
		element.edit()


class RemoveBreakpoint(ActionElement):
	name = 'Remove Breakpoint'
	key = 'remove_breakpoint'
	element = BreakpointView

	def action(self, debugger, element: BreakpointView):
		element.remove()

	def is_visible(self, debugger, element: BreakpointView):
		return element.is_removeable()


class RemoveAllBreakpoints(ActionElement):
	name = 'Remove All Breakpoints'
	key = 'remove_all_breakpoints'
	element = BreakpointView

	def action(self, debugger, element: BreakpointView):
		debugger.breakpoints.remove_all()

	def is_visible(self, debugger, element: BreakpointView):
		return element.is_removeable()
