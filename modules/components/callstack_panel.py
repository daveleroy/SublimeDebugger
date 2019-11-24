from ..typecheck import *
from ..import core, ui, dap
from ..debugger.debugger import DebuggerStateful, ThreadStateful

from .layout import callstack_panel_width
from .import css

import os

class CallStackPanel (ui.div):
	def __init__(self) -> None:
		super().__init__()
		self.threads = [] #type: List[ThreadStateful]

	def update(self, debugger: DebuggerStateful, threads: List[ThreadStateful]) -> None:
		self.threads = threads
		self.debugger = debugger
		for thread in threads:
			thread.on_dirty = self.dirty
		self.dirty()

	def render(self) -> ui.div.Children:
		return list(map(lambda thread: ThreadComponent(self, thread), self.threads))


class ThreadComponent (ui.div):
	def __init__(self, panel: CallStackPanel, thread: ThreadStateful) -> None:
		super().__init__()
		self.panel = panel
		self.thread = thread
		self.fetched = False
		self.debugger = panel.debugger

	def on_select_thread(self) -> None:
		self.thread.debugger.select_threadstateful(self.thread, None)

	def toggle(self) -> None:
		if self.thread.expanded:
			self.thread.collapse()
		else:
			self.thread.expand()

	def on_selected_frame_at(self, index: int) -> None:
		self.thread.debugger.select_threadstateful(self.thread, self.thread.frames[index])

	def render(self) -> ui.div.Children:
		if self.thread.stopped:
			item = ui.div(height=3.0, width=125)[
				ui.click(self.toggle)[
					ui.icon(ui.Images.shared.open if self.thread.expanded else ui.Images.shared.close),
				],
				ui.click(self.on_select_thread)[
					ui.span(height=2, css=css.button)[
						ui.icon(ui.Images.shared.thread_running),
					],
					ui.text(self.thread.name, css=css.label_padding),
				],
			]
		else:
			item = ui.div(height=3.0, width=115)[
				ui.click(self.on_select_thread)[
					ui.span(height=2, css=css.button)[
						ui.icon(ui.Images.shared.thread_running),
					],
					ui.text(self.thread.name, css=css.label_padding),
				],
			]

		items = [item] #type: List[ui.div]

		frames = [] #type: List[ui.div]
		selected_item = None
		for index, frame in enumerate(self.thread.frames):
			def on_click(index=index):
				self.on_selected_frame_at(index)
			component = StackFrameComponent(frame, on_click, width=115)
			items.append(component)
			if self.thread == self.debugger.selected_threadstateful and not self.debugger.selected_thread_explicitly and frame == self.debugger.selected_frame:
				selected_item = component

		if selected_item:
			selected_item.add_class(css.selected.class_name)
		else:
			item.add_class(css.selected.class_name)

		return items


class StackFrameComponent (ui.div):
	def __init__(self, frame: dap.StackFrame, on_click: Callable[[], None], width: float) -> None:
		super().__init__(width=width)
		self.frame = frame
		self.on_click = on_click

	def render(self) -> ui.div.Children:
		frame = self.frame
		name = os.path.basename(frame.file)
		if frame.presentation == dap.StackFrame.subtle:
			color = "secondary"
		else:
			color = "primary"

		assert self.layout
		emWidth = self.layout.em_width()
		padding_left = 0.8
		padding_right = 0.8
		max_length = callstack_panel_width(self.layout) - padding_left - padding_right - 5
		name_length = len(name) * emWidth

		if name_length > max_length:
			name_length = max_length

		max_length -= name_length
		frame_length = max_length

		file_and_line = ui.click(self.on_click)[
			ui.span(height=2, css=css.button)[
				ui.text(str(frame.line), css=css.label),
			],
			ui.text(name, css=css.label_padding),
			ui.text(frame.name, css=css.label_secondary_padding),
		]

		return [
			ui.div(height=3.0, css=css.icon_sized_spacer)[
				file_and_line,
			]
		]
