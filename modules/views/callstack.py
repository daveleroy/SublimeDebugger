from __future__ import annotations
from typing import TYPE_CHECKING, Any

from ..import ui
from ..import core
from .. import dap
from . import css
from .tabbed import TabbedView

from ..output_panel import OutputPanelTabs, OutputPanel

import os

if TYPE_CHECKING:
	from ..debugger import Debugger

class CallStackState:
	def __init__(self):
		self._expanded: dict[int, bool] = {}

	def is_expanded(self, item: Any, default: bool = False):
		expanded = self._expanded.get(id(item))
		if expanded is None:
			return default
		return expanded

	def set_expanded(self, item: Any, value: bool):
		self._expanded[id(item)] = value

	def toggle_expanded(self, item: Any, default: bool = False):
		self._expanded[id(item)] = not self.is_expanded(item, default)



class CallstackView(ui.div, core.Dispose):

	def __init__(self, debugger: Debugger):
		super().__init__()
		self.debugger = debugger
		self.state = CallStackState()

	def added(self):
		self.dispose_add([
			self.debugger.on_session_threads_updated.add(self.dirty_session),
			self.debugger.on_session_active.add(self.dirty_session),
			self.debugger.on_session_added.add(self.dirty_session),
			self.debugger.on_session_removed.add(self.dirty_session),
		])

	def removed(self):
		self.dispose()

	def dirty_session(self, session: dap.Session):
		self.dirty()

	def selected_session(self, session: dap.Session):
		self.debugger.current_session = session

	def render(self):
		if not self.debugger.sessions:
			with ui.div(height=css.row_height):
				ui.spacer(1)
				ui.text('No Active Debug Sessions', css=css.secondary)

			return

		for session in self.debugger.sessions:
			# skip sessions that are children of another session since those will be renderer in the parent session
			if session.parent: continue

			SessionView(self.debugger, session, self.state)


class CallStackTabbedView (TabbedView):
	def __init__(self, debugger: Debugger, panel: OutputPanel):
		super().__init__('Callstack')
		self.debugger = debugger
		self.callstack = CallstackView(self.debugger)
		self.active = self.callstack

		self.tabs = OutputPanelTabs(self.debugger, panel)

	def header(self, is_selected):
		self.tabs.append_stack()
	def render(self):
		self.active.append_stack()

def toggle(toggle_expand, item: ui.span, is_expanded):
	with ui.div(height=css.row_height):
		ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close, on_click=toggle_expand)
		item.append_stack()

class SessionView (ui.div):
	def __init__(self, debugger: Debugger, session: dap.Session, state: CallStackState, prefix: str|None = None):
		super().__init__()
		self.debugger = debugger
		self.session = session
		self.prefix = prefix
		self.state = state
		self.is_selected = session == debugger.session

	def selected_session(self):
		self.debugger.current_session = self.session

	def render(self):
		# if this session has no threads and a single child session then only render the child session and prefix the name with the parent session
		if not self.session.threads and len(self.session.children) == 1:
			for session in self.session.children:
				SessionView(self.debugger, session, self.state, self.session.name)
			return

		if self.prefix:
			name = f'{self.prefix}: {self.session.name}'
		else:
			name = self.session.name

		is_expanded = self.state.is_expanded(self.session, default=True)
		label_view: ui.div | None = None

		if self.session == self.debugger.session:
			session_css_label = css.label
		else:
			session_css_label = css.secondary

		def on_toggle(session: dap.Session):
			self.state.toggle_expanded(session, default=True)
			self.dirty()

		with ui.div(height=css.row_height):
			ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close, on_click=lambda session=self.session: on_toggle(session))
			ui.text(name, css=session_css_label, on_click=lambda session=self.session: self.selected_session())


		if not is_expanded:
			return label_view

		with ui.div(css=css.table_inset):
			for session in self.session.children:
				SessionView(self.debugger, session, self.state)

			for thread in self.session.threads:
				ThreadView(self.debugger, self.session, thread, self.state)


class ThreadView (ui.div):
	def __init__(self, debugger: Debugger, session: dap.Session, thread: dap.Thread, state: CallStackState):
		super().__init__()
		self.debugger = debugger
		self.session = session
		self.is_selected = session.selected_thread == thread and debugger.session == session


		self.show_thread_name = len(session.threads) > 1
		self.thread = thread
		self.state = state
		self.frames: list[dap.StackFrame] = []

		if self.is_selected:
			self.state.set_expanded(thread, True)

		self.fetch()

	@property
	def is_expanded(self):
		return self.state.is_expanded(self.thread) or not self.show_thread_name

	def toggle_expanded(self):
		self.state.toggle_expanded(self.thread)

	@core.run
	async def fetch(self):
		if not self.is_expanded or not self.thread.stopped:
			return

		self.frames = await self.thread.children()
		self.dirty()

	def toggle_expand(self):
		self.toggle_expanded()
		self.fetch()
		self.dirty()

	def on_select_thread(self):
		self.session.set_selected(self.thread, None)

	def on_select_frame(self, frame: dap.StackFrame):
		self.session.set_selected(self.thread, frame)

	def on_select_frame_instructions_view(self):
		self.debugger.show_disassembly()

	def render(self):
		expandable = self.thread.has_children()
		is_expanded = self.is_expanded

		if self.is_selected:
			text_css = css.label
		else:
			text_css = css.secondary


		thread_css = css.selected if self.is_selected and not self.session.selected_frame else None

		def thread_name():
			with ui.span(on_click=self.on_select_thread):
				ui.text(self.thread.name.strip(), css=text_css)
				ui.spacer(1)
				ui.text(self.thread.stopped_reason, css=css.secondary)


		if not self.show_thread_name:
			...
		elif expandable:
			with ui.div(height=css.row_height, css=thread_css):
				ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close, on_click=self.toggle_expand)
				thread_name()

		else:
			with ui.div(height=css.row_height, css=thread_css):
				ui.icon(ui.Images.shared.loading)
				thread_name()


		if not is_expanded:
			return

		for frame in self.frames:
			is_frame_selected = self.is_selected and self.session.selected_frame == frame

			with ui.div(height=css.row_height, css=css.selected if is_frame_selected else None):
				with ui.span(on_click=lambda frame=frame: self.on_select_frame(frame)):
					if (frame.presentationHint == 'label' or frame.presentationHint == 'subtle' or frame.presentationHint == 'deemphasize') or not frame.source or frame.source.presentationHint == 'deemphasize':
						css_label = css.secondary
					else:
						css_label = css.label

					line_str = str(frame.line)

					ui.spacer([1, 3][self.show_thread_name])
					ui.text(frame.name, css=css_label)

					if frame.source:
						name = os.path.basename(frame.source.name or frame.source.path or '??')
						ui.spacer()
						ui.text(name, css=css.secondary)
						ui.spacer(1)
						ui.text(line_str, css=css.button)
