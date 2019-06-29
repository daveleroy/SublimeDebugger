from sublime_debug.modules.core.typecheck import (List, Callable, Optional)

import os

from sublime_debug.modules import ui
from sublime_debug.modules import core

from sublime_debug.modules.debugger_stateful.debugger import (
	Thread,
	StackFrame,
	DebugAdapterClient,
	DebuggerStateful,
	ThreadStateful
)

from .layout import callstack_panel_width


class CallStackPanel (ui.Block):
	def __init__(self) -> None:
		super().__init__()
		self.threads = [] #type: List[ThreadStateful]
		self.thread_components = [] #type: List[ThreadComponent]

	def update(self, debugger: DebuggerStateful, threads: List[ThreadStateful]) -> None:
		self.threads = threads
		self.debugger = debugger
		for thread in threads:
			thread.on_dirty = self.dirty
		self.dirty()

	def render(self) -> ui.Block.Children:
		self.thread_components = []
		for thread in self.threads:
			item = ThreadComponent(self, thread)
			self.thread_components.append(item)
		return [
			ui.Table(items=self.thread_components)
		]


class ThreadComponent (ui.Block):
	def __init__(self, panel: CallStackPanel, thread: ThreadStateful) -> None:
		super().__init__()
		assert isinstance(thread, ThreadStateful)
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
			self.thread.expand();

	def onClicked(self, index: int) -> None:
		self.thread.debugger.select_threadstateful(self.thread, self.thread.frames[index])

	def render(self) -> ui.Block.Children:
		max_length = callstack_panel_width(self.layout) - 6
		if self.thread.stopped:
			item = ui.block(
				ui.Button(self.toggle, items=[
					ui.Img((ui.Images.shared.close, ui.Images.shared.open)[self.thread.expanded]),
				]),
				ui.Button(self.on_select_thread, items=[
					ui.Box(
						ui.Padding(ui.Img(ui.Images.shared.thread), left=0.8, right=0.8)
					),
					ui.Label(self.thread.name, padding_left=0.8, width=max_length, align=0),
				])
			)
		else:
			item = ui.block(
				ui.Button(self.on_select_thread, items=[
					ui.Img(ui.Images.shared.thread_running),
					ui.Box(
						ui.Label("", padding_left=0.8),
						ui.Img(ui.Images.shared.thread),
						ui.Label("", padding_left=0.8),
					),
					ui.Label(self.thread.name, padding_left=0.8, width=max_length, align=0),
				]),
			)

		item = ui.Padding(item, top=0.1, bottom=0.1)
		items = [item] #type: List[ui.Block]

		frames = [] #type: List[ui.Block]
		selected_index = -1
	
		for index, frame in enumerate(self.thread.frames):
			if self.thread == self.debugger.selected_threadstateful and frame == self.debugger.selected_frame:
				selected_index = index

			def on_click(index=index):
				self.onClicked(index)
			component = ui.Padding(StackFrameComponent(frame, on_click), top=0.1, bottom=0.2)
			frames.append(component)

		table = ui.Table(items=frames, selected_index=selected_index)
		items.append(table)

		if self.debugger.selected_threadstateful == self.thread and selected_index == -1:
			item.add_class('selected_stack_frame')

		return items


class StackFrameComponent (ui.Block):
	def __init__(self, frame: StackFrame, on_click: Callable[[], None]) -> None:
		super().__init__()
		self.frame = frame
		self.on_click = on_click

	def render(self) -> ui.Block.Children:
		frame = self.frame
		name = os.path.basename(frame.file)
		if frame.presentation == StackFrame.subtle:
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

		fileAndLine = ui.Button(on_click=self.on_click, items=[
			ui.Box(
				ui.Label(str(frame.line), width=3, color=color),
			),
			ui.Label(name, width=name_length, padding_left=padding_left, padding_right=padding_right, color=color, align=0),
			ui.Label(frame.name, width=frame_length, color="secondary", align=0),
		])
		return [ui.block(fileAndLine)]