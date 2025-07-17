from __future__ import annotations

import struct
import sublime
import base64

import sublime_plugin

from . import dap
from . import core
from . import ui

from .views import css


class InternalMemoryView:
	views: dict[int, InternalMemoryView] = {}

	@staticmethod
	def get(view: sublime.View):
		return InternalMemoryView.views[view.id()]

	def __init__(self, window: sublime.Window, name: str):
		self.name = name
		self.ignore_selection_change = False
		self.selection = None
		self.selection_index = 0
		self.data: list[int | None] = []

		self.view = window.new_file(sublime.ADD_TO_SELECTION | sublime.CLEAR_TO_RIGHT | sublime.SEMI_TRANSIENT)
		InternalMemoryView.views[self.view.id()] = self
		self.view.set_name('☰ ' + self.name + '...')
		self.view.set_scratch(True)
		self.view.assign_syntax(core.package_path_relative('contributes/Syntax/Memory.sublime-syntax'))
		self.view.settings().update(
			{
				'debugger': True,
				'debugger.view': True,
				'debugger.view.memory': True,
				'gutter': False,
				'rulers': [],
				'word_wrap': False,
				'scroll_past_end': False,
			}
		)

	def append_memory(self, response: dap.ReadMemoryResponse):
		storage = core.package_storage_path(ensure_exists=True)
		core.make_directory(f'{storage}/bin')
		file = core.package_path() + '/bin/' + '☰ ' + self.name

		self.view.retarget(file)

		if response.address.startswith('0x'):
			self.address = int(response.address, 16)
		else:
			self.address = int(response.address)

		data = base64.b64decode(response.data) if response.data else b''

		self.data.extend(data)
		if response.unreadableBytes:
			self.data.extend([None] * response.unreadableBytes)

		output = ''
		for i in range(0, len(self.data), 16):
			slice = self.data[i : i + 16]
			output += self.line(slice, self.address + i)

		viewport_position = self.view.viewport_position()

		def edit(edit: sublime.Edit):
			self.view.replace(edit, sublime.Region(0, self.view.size()), output)
			self.view.sel().clear()

		core.edit(self.view, edit)

		# restore the viewport position after replacing all the contents otherwise the view is in the wrong place
		# for some reason if we restore without adjusting it a little then it gets ignored and stays at the bottom of the new content
		self.view.set_viewport_position((viewport_position[0], viewport_position[1] + 0.1), False)

	@core.sublime_edit_method
	def input(self, edit: sublime.Edit, character: str):
		selection = self.selection
		if not selection:
			return
		if not character in '0123456789abcdefABCDEF':
			return

		replace = selection + self.selection_index % 2
		replace_next = selection + (self.selection_index + 1) % 2

		self.view.add_regions('selection_under', [sublime.Region(replace_next, replace_next + 1)], scope='constant.numeric', flags=sublime.DRAW_NO_OUTLINE | sublime.DRAW_NO_FILL | sublime.DRAW_SOLID_UNDERLINE)

		line, data_offset, offset, ascii_offset = self.offset_from_point(replace)

		if self.data[line * 16 + data_offset] is not None:
			self.view.set_scratch(False)
			self.view.replace(edit, sublime.Region(replace, replace + 1), character.upper())

			hex = self.view.substr(sublime.Region(selection, selection + 2))
			byte = int(hex, 16)
			self.data[line * 16 + data_offset] = byte

			region = self.view.full_line(self.view.text_point(line, 0))
			self.view.replace(edit, region, self.line(self.data[line * 16 : line * 16 + 16], self.address + 16 * line))

		self.selection_index += 1

		if self.selection_index < 2:
			return

		if data_offset >= 15:
			self.view.sel().clear()
			self.view.sel().add(self.view.text_point(line + 1, 0))
		else:
			self.view.sel().clear()
			self.view.sel().add(selection + 4)

	def save(self):
		self.view.set_scratch(True)

	def dispose(self):
		self.view.close()
		try:
			del InternalMemoryView.views[self.view.id()]
		except KeyError:
			...

	def slice(self, line: int, offset: int, size: int):
		i = line * 16 + offset
		return self.data[i : i + size]

	def show_popup(self, point: int, line: int, offset: int):
		data = self.slice(line, offset, 16)

		def field(text: str, format: str, length: int):
			with ui.div(height=css.row_height):
				ui.text(text, css=css.button)
				ui.spacer(1)

				try:
					unpacked = struct.unpack('<' + format, bytes(data[:length]))  # type: ignore
					ui.text(f'{unpacked[0]}', css=css.label)
				except TypeError as e:
					ui.text(f'encountered unreadable memory', css=css.redish)
				except Exception as e:
					ui.text(f'{e}', css=css.redish)

		with ui.Popup(self.view, location=point):
			with ui.div(width=32):
				field('  int8', 'b', 1)
				field(' uint8', 'B', 1)
				field(' int16', 'h', 2)
				field('uint16', 'H', 2)
				field(' int32', 'i', 4)
				field('uint32', 'I', 4)
				field(' int64', 'q', 8)
				field('uint64', 'Q', 8)
				field('   f32', 'f', 4)
				field('   f64', 'd', 8)

	def offset_from_point(self, point: int):
		line, column = self.view.rowcol(point)
		string = self.view.substr(self.view.line(point))

		ascii_offset = len(string.split('   ')[0]) + 3
		hex_offset = len(string.split(': ')[0]) + 2

		if column > ascii_offset:
			offset = int((column - ascii_offset) / 2)

		else:
			raw_offset = column - hex_offset - 2
			offset = raw_offset - int(raw_offset / 12)
			offset = offset - int(offset / 3 * 2)

		offset = min(max(0, offset), 15)

		return (line, offset, hex_offset + offset * 3 + int(offset / 12 * 3), ascii_offset + offset * 2)

	def refresh_selection(self):
		sel = self.view.sel()
		if not sel:
			return

		start = sel[0].a
		if sel[0].size() != 0:
			self.view.erase_regions('selection')
			self.view.erase_regions('selection_under')
			return

		sel.clear()

		line, data_offset, offset, ascii_offset = self.offset_from_point(start)
		try:
			self.data[line * 16 + data_offset]
		except IndexError:
			return  # data out of range

		ascii_point = self.view.text_point(line, ascii_offset)
		point = self.view.text_point(line, offset)

		self.show_popup(point, line, data_offset)

		self.selection = point
		self.selection_index = 0

		self.view.add_regions('selection', [sublime.Region(point, point + 2), sublime.Region(ascii_point, ascii_point + 1)], scope='region.bluish debugger.selection', flags=sublime.DRAW_NO_OUTLINE)
		self.view.erase_regions('selection_under')

	def line(self, data: list[int | None], address: int):
		output = ''
		output_data = ''

		output += hex(address + 0).upper()[2:].zfill(8)
		output += ':'

		for i in range(0, 0 + len(data)):
			try:
				c = data[i]
			except IndexError:
				break

			if i != 0 and i % 4 == 0:
				output += '  '

			elif (i) % 1 == 0:
				output += ' '

			if c is None:
				output += '..'
				output_data += '. '
				continue

			character = '{:02x}'.format(c)
			output += character.upper()

			rep = chr(c)
			output_data += rep if rep.isprintable() else '.'
			output_data += ' '

		output += '   '
		output += output_data.replace('\n', '\\n')
		output += '\n'
		return output


class MemoryView(InternalMemoryView):
	def __init__(self, window: sublime.Window, debugger: dap.Debugger, session: dap.Session, memory_reference: str):
		super().__init__(window, memory_reference)

		self.window = window
		self.debugger = debugger
		self.session = session
		self.memory_reference = memory_reference

		self.error = None
		self.page_size = 1024 * 4

		self.timer = core.timer(self._check_if_requires_fetching, 1.0, True)

		self.load_next_page()

	def load_next_page(self):
		async def load():
			try:
				response = await self.session.read_memory(self.memory_reference, self.page_size, len(self.data))
				self.append_memory(response)

			except dap.Error as error:
				self.error = error

		self.loading = core.run(load())

	def _check_if_requires_fetching(self):
		if self.error:
			return

		viewport_height = self.view.viewport_extent()[1]

		height = self.view.layout_extent()[1]
		offset = self.view.viewport_position()[1] + self.view.viewport_extent()[1]

		if height - offset <= viewport_height and self.loading.done():
			core.info('loading next memory page')
			self.load_next_page()

	def dispose(self):
		self.timer.dispose()
		return super().dispose()

	def save(self):
		super().save()
		sublime.error_message('Sorry, modifying memory is not currently supported')


class DebuggerMemoryViewListener(sublime_plugin.ViewEventListener):
	@classmethod
	def is_applicable(cls, settings: sublime.Settings) -> bool:
		return bool(settings.get('debugger.view.memory'))

	def __init__(self, view: sublime.View) -> None:
		super().__init__(view)
		try:
			self.memory = InternalMemoryView.get(view)
		except KeyError:
			view.set_scratch(True)
			view.close()

		self.data = ''

	def on_selection_modified(self):
		self.memory.refresh_selection()

	def on_pre_save(self) -> None:
		self.memory.save()

		# remove all the data we don't want to save it
		# this will be restored in on_post_save
		def edit(edit):
			self.data = self.view.substr(sublime.Region(0, self.view.size()))
			self.view.replace(edit, sublime.Region(0, self.view.size()), '')

		core.edit(self.view, edit)

	def on_post_save(self):
		def edit(edit):
			self.view.replace(edit, sublime.Region(0, self.view.size()), self.data)
			self.data = ''

		core.edit(self.view, edit)


class DebuggerMemoryInput(sublime_plugin.TextCommand):
	def run(self, edit, character):  # type: ignore
		print(character)
		InternalMemoryView.get(self.view).input(character)


# def run():
# 	memory = MemoryView(sublime.active_window())
# 	memory.update(dap.ReadMemoryResponse.from_json({'address': '0x7FFEEFBFF958', 'data': 'oEFAAAEAAADIQUAAAQAAAKBBQAABAAAAkPm/7/5/AACg+b/v/n8AAMD4v+/+fwAABAAAAAUAAACgQUAAAQAAAMhBQAABAAAA4EFAAAEAAACWADDRBQAAAOD5v+/+fwAAmkcAAAEAAAAAAAAAAAAAAJj6v+/+fwAAAPq/7/5/AAABAAAAAAAAAPD5v+/+fwAAXf87IP9/AAAAAAAAAAAAAAEAAAAAAAAAYPu/7/5/AAAAAAAAAAAAALr7v+/+fwAA0Pu/7/5/AAD3+7/v/n8AABL8v+/+fwAAIPy/7/5/AAAy/L/v/n8AADv8v+/+fwAAafy/7/5/AACU/b/v/n8AANb9v+/+fwAA/P2/7/5/AAA1/r/v/n8AANBAQAABAAAAUv6/7/5/AABh/r/v/n8AAHT+v+/+fwAAz/6/7/5/AAAAAAAAAAAAAPD6v+/+fwAA4P6/7/5/AADz/r/v/n8AABL/v+/+fwAAR/+/7/5/AABk/7/v/n8AAKD/v+/+fwAAx/+/7/5/AADw/7/v/n8AAAAAAAAAAAAAZXhlY3V0YWJsZV9wYXRoPS9Vc2Vycy9kYXZpZC9MaWJyYXJ5L0FwcGxpY2F0aW9uIFN1cHBvcnQvU3VibGltZSBUZXh0L1BhY2thZ2VzL0RlYnVnZ2VyL2V4YW1wbGVzL2NwcC90ZXM=', 'unreadableBytes': 0}))

# sublime.set_timeout(run, 500)
