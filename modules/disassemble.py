from __future__ import annotations
from typing import Any
from .settings import Settings
import sublime

from .import dap
from .import core

from .views.selected_line import SelectedLine

def view_replace_contents(view: sublime.View, contents: str):
	def edit(edit: sublime.Edit):
		view.replace(edit, sublime.Region(0, view.size()), contents)
		view.sel().clear()

	core.edit(view, edit)


class DisassembleView(core.Dispose):
	def __init__(self, window: sublime.Window, debugger: dap.Debugger):
		self.view = window.new_file(sublime.ADD_TO_SELECTION|sublime.CLEAR_TO_RIGHT|sublime.SEMI_TRANSIENT)
		self.view.set_name('☰ Disassembly')
		self.view.set_scratch(True)
		self.view.assign_syntax(core.package_path_relative('contributes/Syntax/Disassembly.sublime-syntax'))

		settings = self.view.settings()
		settings.update({
			'debugger': True,
			'debugger.view': True,
			'debugger.view.disassemble': True,

			'gutter': False,
			'rulers': [],
			'word_wrap': False,
		})

		self.debugger = debugger

		self._session: dap.Session|None = None
		self._selection = None
		self._selection_index = 0
		self._regions: list[sublime.Region] = []
		self._selected_line: SelectedLine|None = None

		self._loading = None


		self.dispose_add([
			self.debugger.on_session_active.add(self._on_session_active),
			core.timer(self._check_if_requires_fetching, 0.5, True),
		])

		self._on_session_active()


	def dispose(self):
		super().dispose()

		self.view.close()
		if self._selected_line:
			self._selected_line.dispose()
			self._selected_line = None

	@property
	def session(self):
		return self._session

	@session.setter
	def session(self, session: dap.Session|None):
		self._session = session
		if not session:
			view_replace_contents(self.view, 'Disassembly not available')

	@core.run
	async def _on_session_active(self, _: Any = None):
		if self._selected_line:
			self._selected_line.dispose()
			self._selected_line = None

		session = self.debugger.session
		if not session:
			self.session = None
			return

		thread = session.selected_thread
		frame = session.selected_frame

		if not thread or not frame:
			self.session = None
			return

		memory_reference = session.selected_frame and session.selected_frame.instructionPointerReference
		if not memory_reference:
			self.session = None
			return

		if not session.capabilities.supportsDisassembleRequest:
			self.session = None
			return

		self.session = session
		self.memory_reference = memory_reference

		self.memory_offset_start = -64
		self.memory_offset_end = 64

		view_replace_contents(self.view, '')

		self._loading = self._disassemble_and_insert(0, memory_reference,  -64, 128, select_line=64)
		await self._loading



	@core.run
	async def _disassemble_and_insert(self, at: int, memory_reference: str, offset: int, count: int, select_line: int|None = None):
		if not self.session:
			core.info('not loading memory, no session')
			return

		core.info(f'loading memory @{offset}-{offset + count}')

		response = await self.session.disassemble(memory_reference, offset, count)
		contents = '\n'.join(map(lambda instruction: f'{instruction.address}: {instruction.instruction}', response.instructions))

		def edit(edit: sublime.Edit):

			self.view.insert(edit, at, '\n')
			self.view.insert(edit, at, contents)
			if Settings.development:
				if offset > 0:
					self.view.insert(edit, at, f'; + {offset}\n')
				else:
					self.view.insert(edit, at, f'; - {-offset}\n')

			self.view.sel().clear()

		core.edit(self.view, edit)

		if select_line is not None:
			select_line += 2 # we inserted a \n and these lines are 0 based where as
			self._selected_line = SelectedLine(self.view, select_line, None, self.session.selected_thread)
			self.view.show_at_center(self.view.text_point(select_line-1, 0), animate=False)

		return at + 1

	@core.run
	async def _check_if_requires_fetching(self):
		if not self.session:
			return

		if self._loading and not self._loading.done():
			return

		viewport_height = self.view.viewport_extent()[1]

		height = self.view.layout_extent()[1]
		offset = self.view.viewport_position()[1]

		if offset <= viewport_height:
			self._loading = self._disassemble_and_insert(0, self.memory_reference, self.memory_offset_start - 128, 128)
			self.memory_offset_start -= 128

		if height - offset - viewport_height <= viewport_height:
			self._loading = self._disassemble_and_insert(self.view.size(), self.memory_reference, self.memory_offset_end, 128)
			self.memory_offset_end += 128
