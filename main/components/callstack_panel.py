
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

class CallStackPanel (ui.Component):
	def __init__(self) -> None:
		super().__init__()
		self.threads = [] #type: List[Thread]
		self.selected = 0 #type: int
		self.thread_components = [] #type: List[ThreadComponent]

	def dirty_threads(self) -> None:
		for thread_component in self.thread_components:
			thread_component.dirty()

	def update(self, debugger: DebuggerState, threads: List[Thread]) -> None:
		self.threads = threads
		self.debugger = debugger
		self.dirty()
		
	def render(self) -> ui.components:			
		self.thread_components = []
		for thread in self.threads:
			item = ThreadComponent(self.debugger, thread)
			self.thread_components.append(item)
		return [
			ui.HorizontalSpacer(250),
			ui.Panel(items = [
				ui.Segment(items = [
					ui.Label('Call Stack')
				]),
				ui.Table(items = self.thread_components)
			])
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

		fileAndLine = ui.Button(on_click = self.on_click, items = [
			# line number
			ui.Box(items = [
				ui.Label(str(frame.line), width = 3, color = color),
			]),
			# filename
			ui.Label(name, padding_left = 0.8, padding_right = 0.8, color = color),
			ui.Label(frame.name, color="secondary"),
		])
		
		return [
			fileAndLine
		]

class ThreadComponent (ui.Component):
	def __init__(self, debugger: DebuggerState, thread: Thread) -> None:
		super().__init__()
		self.thread = thread
		self.fetched = False
		self.debugger = debugger
		self.frames = [] #type: List[StackFrame]
		self.fetch_frames_if_needed()

		# If there is not an active selected frame or thread we select this thread
		# it will be the first thread in the list
		if thread.stopped and not self.debugger.thread and not self.debugger.frame:
			self.on_select_thread()

	def on_select_thread(self) -> None:
		self.debugger.set_selected_thread(self.thread)

	def toggle (self) -> None:
		self.thread.expanded = not self.thread.expanded
		self.fetch_frames_if_needed()
		self.dirty()

	def fetch_frames_if_needed(self) -> None:
		if self.thread.stopped and self.thread.expanded and not self.fetched:
			self.fetched = True
			def response(frames: List[StackFrame]) -> None:
				if frames and not self.debugger.frame:
					self.debugger.set_selected_frame(frames[0])
				self.frames = frames
				self.dirty()
					
			core.run(self.thread.client.GetStackTrace(self.thread), response)

	def onClicked(self, index: int) -> None:
		frame = self.frames[index]
		self.debugger.set_selected_frame(frame)

	def render (self) -> ui.components:
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
					ui.Label(self.thread.name, padding_left = 0.8),
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
					ui.Label(self.thread.name, padding_left = 0.8, padding_right = 0.8),
					ui.Label('running', color="secondary"),
				]),
			])

		items = [item] #type: List[ui.Component]
			
		if self.thread.expanded and self.thread.stopped:
			frames = [] #type: List[ui.Component]
			selected_index = -1
			for index, frame in enumerate(self.frames):
				on_click = lambda index=index: self.onClicked(index) #type: ignore
				component = StackFrameComponent(self.debugger, frame, on_click)

				# if a thread is not selected and a frame is selected we select that index in the table
				if not self.debugger.thread and self.debugger.frame and self.debugger.frame == frame:
					selected_index = index

				frames.append(component)
			
			table = ui.Table(items = frames, selected_index = selected_index)
			items.append(table)

		if self.debugger.thread and self.debugger.thread == self.thread:
			item.add_class('selected')
			
		return items

