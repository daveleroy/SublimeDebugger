from __future__ import annotations
from ..typecheck import*

from ..import ui
from ..import core
from .. import dap
from . import css

import os

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

class CallStackView (ui.div):
	def __init__(self, sessions: dap.Sessions):
		super().__init__()
		self.sessions = sessions
		self.state = CallStackState()

	def added(self, layout: ui.Layout):
		self.on_updated = self.sessions.on_updated_threads.add(self.on_threads_updated)
		self.on_selected = self.sessions.on_selected.add(self.on_threads_updated)
		self.on_added_session = self.sessions.on_added_session.add(self.on_threads_updated)
		self.on_removed_session = self.sessions.on_removed_session.add(self.on_threads_updated)

	def removed(self):
		self.on_updated.dispose()
		self.on_added_session.dispose()
		self.on_removed_session.dispose()

	def on_threads_updated(self, session: dap.Session):
		self.dirty()

	def selected_session(self, session: dap.Session):
		self.sessions.active = session

	def render(self) -> ui.div.Children:
		thread_views: list[SessionView] = []
		show_session_name = len(self.sessions.sessions) > 1

		if not self.sessions.sessions:
			return ui.div(height=css.row_height)[
				ui.spacer(1),
				ui.text('No Active Debug Sessions', css=css.label_secondary)
			]

		for session in self.sessions:
			if session.parent: continue


			# for thread in threads:
			# 	is_selected = session == self.sessions.selected_session and session.selected_thread == thread
			# 	if is_selected:
			# 		self.state.set_expanded(thread, True)

			thread_views.append(SessionView(self.sessions, session, self.state))

		return thread_views

def toggle(toggle_expand, item: ui.span, is_expanded) -> ui.div:
	return ui.div(height=css.row_height)[
		ui.align()[
			ui.click(toggle_expand)[
				ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close)
			],
			item,
			# self.item_right,
		]
	]

class SessionView (ui.div):
	def __init__(self, sessions: dap.Sessions, session: dap.Session, state: CallStackState):
		super().__init__()
		self.sessions = sessions
		self.session = session
		self.state = state
		self.is_selected = session == sessions.selected_session
		self.show_session_name = True

	def selected_session(self):
		self.sessions.active = self.session

	def render(self) -> ui.div.Children:
		session = self.session
		threads = session.threads
		expanded = self.state.is_expanded(session, default=True)
		thread_views: list[SessionView|ThreadView] = []
		label_view: ui.div | None = None


		if True:
			if session == self.sessions.active:
				session_css_label = css.label
			else:
				session_css_label = css.label_secondary

			session_label = ui.click(lambda session=session: self.selected_session()) [
				ui.text(session.name, css=session_css_label)
			]

			def on_toggle(session: dap.Session):
				self.state.toggle_expanded(session, default=True)
				self.dirty()

			label_view = toggle(lambda session=session: on_toggle(session), session_label, expanded)


		if not expanded:
			return label_view
			
		for session in self.session.children:
			thread_views.append(SessionView(self.sessions, session, self.state))

		show_thread_name = len(threads) > 1

		for thread in threads:
			is_selected = self.is_selected and session.selected_thread == thread
			if is_selected:
				self.state.set_expanded(thread, True)

			thread_views.append(ThreadView(session, thread, is_selected, self.state, show_thread_name))

		return [
			label_view,
			ui.div(css=css.table_inset)[
				thread_views
			]
		]

class ThreadView (ui.div):
	def __init__(self, session: dap.Session, thread: dap.Thread, is_selected: bool, state: CallStackState, show_thread_name: bool):
		super().__init__()
		self.session = session
		self.is_selected = is_selected
		self.show_thread_name = show_thread_name
		self.thread = thread
		self.state = state
		self.frames = [] #type: list[dap.StackFrame]
		self.fetch()

	@property
	def is_expanded(self):
		return self.state.is_expanded(self.thread) or not self.show_thread_name

	def toggle_expanded(self):
		self.state.toggle_expanded(self.thread)

	@core.schedule
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

	def render(self) -> ui.div.Children:
		expandable = self.thread.has_children()
		is_expanded = self.is_expanded

		if expandable:
			thread_item = ui.div(height=css.row_height)[
				ui.align()[
					ui.click(self.toggle_expand)[
						ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close),
					],
					ui.click(self.on_select_thread)[
						ui.text(self.thread.name, css=css.label),
						ui.spacer(1),
						ui.text(self.thread.stopped_reason, css=css.label_secondary),
					],
				]
			]
		else:
			thread_item = ui.div(height=css.row_height)[
				ui.icon(ui.Images.shared.loading),
				ui.click(self.on_select_thread)[
					ui.text(self.thread.name, css=css.label),
					ui.spacer(1),
					ui.text(self.thread.stopped_reason, css=css.label_secondary),
				],
			]

		if self.is_selected and not self.session.selected_frame:
			thread_item.add_class(css.selected.class_name)

		if not self.show_thread_name:
			thread_item = ui.div()

		if is_expanded:
			return [
				thread_item,
				ui.div()[
					[StackFrameComponent(self.session, frame, self.is_selected and self.session.selected_frame == frame, lambda frame=frame: self.on_select_frame(frame), self.show_thread_name) for frame in self.frames] #type: ignore
				]
			]
		else:
			return thread_item


class StackFrameComponent (ui.div):
	def __init__(self, session: dap.Session, frame: dap.StackFrame, is_selected: bool, on_click: Callable[[], None], show_thread_name: bool) -> None:
		super().__init__()
		self.frame = frame
		self.on_click = on_click
		self.show_thread_name = show_thread_name
		if is_selected:
			self.add_class(css.selected.class_name)

	def render(self) -> ui.div.Children:
		frame = self.frame
		source = frame.source

		if (frame.presentation == dap.StackFrame.label or frame.presentation == dap.StackFrame.subtle or frame.presentation == dap.StackFrame.deemphasize) or (source and source.presentationHint == dap.Source.deemphasize):
			css_label = css.label_secondary
		else:
			css_label = css.label

		line_str = str(frame.line)

		items: list[ui.span] = [
			ui.spacer([1, 3][self.show_thread_name]),
			ui.text(frame.name, css=css_label),
		]

		if source:
			name = os.path.basename(source.name or source.path or '??')
			items.append(ui.spacer(min=1))
			items.append(ui.text(name, css=css.label_secondary))
			items.append(ui.spacer(1))
			items.append(ui.text(line_str, css=css.button))

		file_and_line = ui.click(self.on_click)[
			ui.align()[
				items
			]
		]

		return [
			ui.div(height=css.row_height)[
				file_and_line,
			]
		]
