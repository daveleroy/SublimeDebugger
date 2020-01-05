from ...typecheck import*
from ...import ui
from ...import core
from ...import dap

from ..debugger_session import DebuggerSession, Threads, Thread

from .layout import callstack_panel_width
from . import css

import os


class State:
	def __init__(self):
		self._expanded = {}

	def is_expanded(self, item: Any):
		return self._expanded.get(id(item)) is not None

	def set_expanded(self, item: Any, value: bool):
		if value:
			self._expanded[id(item)] = True
		else:
			del self._expanded[id(item)]

	def toggle_expanded(self, item: Any):
		if self.is_expanded(item):
			del self._expanded[id(item)]
		else:
			self._expanded[id(item)] = True


class CallStackView (ui.div):
	def __init__(self, debugger: DebuggerSession):
		super().__init__()
		self.debugger = debugger
		self.state = State()

	def added(self, layout: ui.Layout):
		self.on_updated = self.debugger.callstack.on_updated.add(self.dirty)

	def removed(self):
		self.on_updated.dispose()

	def render(self) -> ui.div.Children:
		threads = self.debugger.callstack.threads
		if self.debugger.callstack.selected_thread:
			self.state.set_expanded(self.debugger.callstack.selected_thread, True)

		return [ThreadView(self.debugger, thread, self.state, len(threads) == 1) for thread in threads]


class ThreadView (ui.div):
	def __init__(self, debugger: DebuggerSession, thread: Thread, state: State, hide_name: bool):
		super().__init__()
		self.debugger = debugger
		self.hide_name = hide_name
		self.thread = thread
		self.state = state
		self.frames = [] #type: List[dap.StackFrame]
		core.run(self.fetch())

	@core.coroutine
	def fetch(self):
		if not self.state.is_expanded(self.thread):
			return []

		self.frames = yield from self.thread.children()
		self.dirty()

	def toggle_expand(self):
		self.state.toggle_expanded(self.thread)
		core.run(self.fetch())
		self.dirty()

	def on_select_thread(self):
		self.debugger.callstack.set_selected(self.thread, None)

	def on_select_frame(self, frame: dap.StackFrame):
		self.debugger.callstack.set_selected(self.thread, frame)

	def render(self) -> ui.div.Children:
		width = callstack_panel_width(self.layout)
		expandable = self.thread.has_children()
		is_expanded = self.state.is_expanded(self.thread)

		if expandable:
			thread_item = ui.div(height=3.0, width=width)[
				ui.click(self.toggle_expand)[
					ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close),
				],
				ui.click(self.on_select_thread)[
					ui.span(height=0, css=css.button)[
						ui.icon(ui.Images.shared.thread_running),
					],
					ui.text(self.thread.name, css=css.label_padding),
				],
			]
		else:
			thread_item = ui.div(height=3.0, width=width)[
				ui.icon(ui.Images.shared.loading),
				ui.click(self.on_select_thread)[
					ui.span(height=0, css=css.button)[
						ui.icon(ui.Images.shared.thread_running),
					],
					ui.text(self.thread.name, css=css.label_padding),
				],
			]

		if not self.debugger.callstack.selected_frame and self.debugger.callstack.selected_thread is self.thread:
			thread_item.add_class(css.selected.class_name)

		if self.hide_name:
			thread_item = ui.div()

		if is_expanded:
			return [
				thread_item,
				ui.div()[
					[StackFrameComponent(self.debugger, frame, lambda frame=frame: self.on_select_frame(frame), width=width) for frame in self.frames] #type: ignore
				]
			]
		else:
			return thread_item


class StackFrameComponent (ui.div):
	def __init__(self, debugger: DebuggerSession, frame: dap.StackFrame, on_click: Callable[[], None], width: float) -> None:
		super().__init__(width=width)
		self.frame = frame
		self.on_click = on_click

		if debugger.callstack.selected_frame is frame:
			self.add_class(css.selected.class_name)

	def render(self) -> ui.div.Children:
		frame = self.frame
		name = os.path.basename(frame.file)
		if frame.presentation == dap.StackFrame.subtle:
			label_padding = css.label_secondary_padding
		else:
			label_padding = css.label_padding

		file_and_line = ui.click(self.on_click)[
			ui.span(css=css.button)[
				ui.text(str(frame.line), css=css.label),
			],
			ui.text_align(self._width, [
				ui.text(name, css=label_padding),
				ui.text(frame.name, css=css.label_secondary_padding),
			])
		]

		return [
			ui.div(height=3.0, css=css.icon_sized_spacer)[
				file_and_line,
			]
		]
