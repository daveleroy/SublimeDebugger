import os
from debug import ui

from debug.core.typecheck import List, Callable, Union

from debug.main.debug_adapter_client.client import DebugAdapterClient
from debug.main.debug_adapter_client.types import StackFrame, Thread

class StackFrameComponent (ui.Component):
	def __init__(self, debugger: DebugAdapterClient, frame: StackFrame, on_click: Callable[[], None]) -> None:
		super().__init__()
		self.frame = frame
		self.debugger = debugger
		self.on_click = on_click
		
	def render (self) -> ui.components:
		frame = self.frame
		name = os.path.basename(frame.file)
		
		fileAndLine = ui.Button(on_click = self.on_click, items = [
			# line number
			ui.Box(items = [
				ui.Label(str(frame.line), width = 3),
			]),
			# filename
			ui.Label(name, padding_left = 0.8, padding_right = 0.8),
			ui.Label(frame.name, color="secondary"),
		])
		className = ""
		selected = False
		selected_frame = self.debugger.selected_frame
		if selected_frame and frame.id == selected_frame.id:
			className = ("StackframeSelected", "StackframeSelectedError")[self.debugger.stoppedOnError]
		
		return [
			fileAndLine
		]
class ThreadComponent (ui.Component):
	def __init__(self, debugger: DebugAdapterClient, thread: Thread) -> None:
		super().__init__()
		self.thread = thread
		self.fetched = False
		self.debugger = debugger
		self.frames = [] #type: List[StackFrame]
		self.fetch_frames_if_needed()

	def on_select_thread(self) -> None:
		pass # TODO allow running commands on this specific thread
		
	def toggle (self) -> None:
		self.thread.expanded = not self.thread.expanded
		self.fetch_frames_if_needed()
		self.dirty()

	def fetch_frames_if_needed(self) -> None:
		if self.thread.expanded and not self.fetched:
			self.fetched = True
			def response(response: List[StackFrame]) -> None:
				self.frames = response
				self.dirty()
					
			self.debugger.getStackTrace(self.thread, response)

	def onClicked(self, index: int) -> None:
		frame = self.frames[index]
		self.debugger.set_selected_thread_and_frame(self.thread, frame)
		self.dirty()

	def render (self) -> ui.components:
		if self.thread.stopped:
			items = [
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
			] #type: List[ui.Component]
		else:
			items = [
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
			]

		if self.thread.expanded and self.thread.stopped:
			frames = [] #type: List[ui.Component]
			selected_index = -1
			for index, frame in enumerate(self.frames):
				on_click = lambda index=index: self.onClicked(index) #type: ignore
				component = StackFrameComponent(self.debugger, frame, on_click)
				if frame == self.debugger.selected_frame:
					selected_index = index
					print('selected_index is', index)
				frames.append(component)
			
			table = ui.Table(items = frames, selected_index = selected_index)
			items.append(table)

		return items

