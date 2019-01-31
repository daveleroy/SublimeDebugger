
import os

from sublime_db.core.typecheck import (List, Callable, Optional)
from sublime_db import ui
from sublime_db import core

from sublime_db.main.debugger import (
	Thread,
	StackFrame,
	DebugAdapterClient,
	DebuggerState
)

from . import constants

class CallStackPanel (ui.Component):
	def __init__(self) -> None:
		super().__init__()
		self.threads = [] #type: List[Thread]
		self.selected_thread = None #type: Optional[Thread]
		self.selected_frame_index = None #type: Optional[int]
		self.thread_components = [] #type: List[ThreadComponent]


	def set_selected(self, thread: Thread, frame: Optional[StackFrame], index: int) -> None:
		self.debugger.set_selected_thread(thread)
		if frame:
			self.debugger.set_selected_frame(frame)
		self.selected_thread = thread
		self.selected_frame_index = index
		self.dirty_threads()

	def has_selection(self) -> bool:
		return self.selected_thread is not None
	def has_selection_frame(self) -> bool:
		return self.selected_frame_index is not None

	def dirty_threads(self) -> None:
		for thread_component in self.thread_components:
			thread_component.dirty()

	def dirty(self) -> None:
		super().dirty()
		print('DIRTY')

	def update(self, debugger: DebuggerState, threads: List[Thread]) -> None:
		self.threads = threads
		self.debugger = debugger
		self.dirty()
		self.dirty_threads()
		for thread in threads:
			print(str(thread.stopped))
	def render(self) -> ui.components:			
		self.thread_components = []
		for thread in self.threads:
			item = ThreadComponent(self, thread)
			self.thread_components.append(item)
		return [
			ui.Table(items = self.thread_components)
		]

class StackFrameComponent (ui.Component):
	def __init__(self, debugger: DebuggerState, frame: StackFrame, on_click: Callable[[], None]) -> None:
		super().__init__()
		self.frame = frame
		self.debugger = debugger
		self.on_click = on_click

	def render (self) -> ui.components:
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
		max_length = constants.PANEL_CONTENT_MAX_WIDTH - padding_left - padding_right - 5
		name_length = len(name) * emWidth

		if name_length > max_length:
			name_length = max_length

		max_length -= name_length
		frame_length = max_length

		fileAndLine = ui.Button(on_click = self.on_click, items = [
			ui.Box(items = [
				ui.Label(str(frame.line), width = 3, color = color),
			]),
			ui.Label(name, width = name_length, padding_left = padding_left, padding_right = padding_right, color = color, align = 0),
			ui.Label(frame.name, width = frame_length, color="secondary", align = 0),
		])
		
		return [
			fileAndLine
		]

class ThreadComponent (ui.Component):
	def __init__(self, panel: CallStackPanel, thread: Thread) -> None:
		super().__init__()
		self.panel = panel
		self.thread = thread
		self.fetched = False
		self.debugger = panel.debugger
		self.frames = [] #type: List[StackFrame]
		self.fetch_frames_if_needed()

		# If there is not an active selected frame or thread we select this thread
		# it will be the first thread in the list
		if thread.stopped and not self.panel.has_selection():
			self.on_select_thread()

	def on_select_thread(self) -> None:
		self.panel.set_selected(self.thread, None, None)

	def toggle (self) -> None:
		self.thread.expanded = not self.thread.expanded
		self.fetch_frames_if_needed()
		self.dirty()

	def fetch_frames_if_needed(self) -> None:
		if self.thread.stopped and self.thread.expanded and not self.fetched:
			self.fetched = True
			print('fetching thread frames')
			def response(frames: List[StackFrame]) -> None:
				if frames and self.panel.selected_thread == self.thread and not self.panel.has_selection_frame():
					self.panel.set_selected(self.thread, frames[0], 0)
				self.frames = frames
				self.dirty()
					
			core.run(self.thread.client.GetStackTrace(self.thread), response)

	def onClicked(self, index: int) -> None:
		self.panel.set_selected(self.thread, self.frames[index], index)

	def render (self) -> ui.components:
		max_length = constants.PANEL_CONTENT_MAX_WIDTH - 5
		if self.thread.stopped:
			item = ui.Items([
				ui.Button(self.toggle, items = [
					ui.Img((ui.Images.shared.right, ui.Images.shared.down)[self.thread.expanded ]),
				]),
				ui.Button(self.on_select_thread, items = [
					ui.Box(items = [
						ui.Label("", padding_left = 0.8),
						ui.Img(ui.Images.shared.thread),
						ui.Label("", padding_left = 0.8),
					]),
					ui.Label(self.thread.name, padding_left = 0.8, width = max_length, align = 0),
				])
			])
		else:
			item = ui.Items([
				ui.Button(self.on_select_thread, items = [
					ui.Img(ui.Images.shared.thread_running),
					ui.Box(items = [
						ui.Label("", padding_left = 0.8),
						ui.Img(ui.Images.shared.thread),
						ui.Label("", padding_left = 0.8),
					]),
					ui.Label(self.thread.name, padding_left = 0.8, width = max_length, align = 0),

				]),
			])

		items = [item] #type: List[ui.Component]
			
		if self.thread.expanded and self.thread.stopped:
			frames = [] #type: List[ui.Component]
			selected_index = -1
			if self.panel.selected_thread == self.thread and self.panel.has_selection_frame():
				selected_index = self.panel.selected_frame_index

			for index, frame in enumerate(self.frames):
				on_click = lambda index=index: self.onClicked(index) #type: ignore
				component = StackFrameComponent(self.debugger, frame, on_click)
				frames.append(component)
			
			table = ui.Table(items = frames, selected_index = selected_index)
			items.append(table)

		if self.panel.selected_thread == self.thread and not self.panel.has_selection_frame():
			item.add_class('selected')
			
		return items

