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
		return list(map(lambda thread: ThreadComponent(self, thread, show_thread_name=len(self.threads) > 1), self.threads))


class ThreadComponent (ui.div):
	def __init__(self, panel: CallStackPanel, thread: ThreadStateful, show_thread_name: bool) -> None:
		super().__init__()
		self.panel = panel
		self.thread = thread
		self.fetched = False
		self.show_thread_name = show_thread_name
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
		width = callstack_panel_width(self.layout)

		frames = [] #type: List[ui.div]
		selected_item = None
		for index, frame in enumerate(self.thread.frames):
			def on_click(index=index):
				self.on_selected_frame_at(index)
			component = StackFrameComponent(frame, on_click, width=width)
			frames.append(component)
			if self.thread == self.debugger.selected_threadstateful and not self.debugger.selected_thread_explicitly and frame == self.debugger.selected_frame:
				selected_item = component

		if selected_item:
			selected_item.add_class(css.selected.class_name)

		if not self.show_thread_name:
			return frames

		if self.thread.stopped:
			item = ui.div(height=3.0, width=width)[
				ui.click(self.toggle)[
					ui.icon(ui.Images.shared.open if self.thread.expanded else ui.Images.shared.close),
				],
				ui.click(self.on_select_thread)[
					ui.span(height=0, css=css.button)[
						ui.icon(ui.Images.shared.thread_running),
					],
					ui.text(self.thread.name, css=css.label_padding),
				],
			]
		else:
			item = ui.div(height=3.0, width=width)[
				ui.click(self.on_select_thread)[
					ui.span(height=0, css=css.button)[
						ui.icon(ui.Images.shared.thread_running),
					],
					ui.text(self.thread.name, css=css.label_padding),
				],
			]

		if not selected_item:
			item.add_class(css.selected.class_name)

		return [
			item,
			ui.div()[
				frames
			]
		]


class StackFrameComponent (ui.div):
	def __init__(self, frame: dap.StackFrame, on_click: Callable[[], None], width: float) -> None:
		super().__init__(width=width)
		self.frame = frame
		self.on_click = on_click

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
			ui.text(name, css=label_padding),
			ui.text(frame.name, css=css.label_secondary_padding),
		]

		return [
			ui.div(height=3.0, css=css.icon_sized_spacer)[
				file_and_line,
			]
		]
