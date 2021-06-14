from __future__ import annotations
from .typecheck import *

from .import core
from .import dap

import re
import sublime
import os

from dataclasses import dataclass

default_file_regex = re.compile("(.*):([0-9]+):([0-9]+): error: (.*)")

class Line:
	def __init__(self, type: str|None, cwd: str|None = None):
		self.type = type
		self.line = ''
		self.cwd = cwd
		self.source: Optional[dap.SourceLocation] = None
		self.variable: Optional[dap.Variable] = None
		self.finished = False

	def add(self, text: str, source: Optional[dap.SourceLocation], file_regex: Any):
		if self.finished:
			raise core.Error('line is already complete')

		is_end_of_line = (text[-1] == '\n' or text[-1] == '\r')

		self.source = self.source or source
		self.line += text.rstrip('\r\n').replace('\t', '    ')

		if is_end_of_line:
			self.commit(file_regex)

	def commit(self, file_regex):
		self.finished = True

		if match := file_regex.match(self.line):
			groupdict = match.groupdict()
			file = groupdict.get("file") or match.group(1)
			line = int(groupdict.get("line") or match.group(2) or 1)

			if len(match.groups()) == 4:
				column = int(groupdict.get("column") or match.group(3) or 1)
			else:
				column = 1

			if not os.path.isabs(file) and self.cwd:
				file = os.path.join(self.cwd, file)

			source = dap.SourceLocation.from_path(file, line, column)

			self.type = 'terminal.error'
			self.source = source

	def add_variable(self, variable: dap.Variable, source: Optional[dap.SourceLocation]):
		if self.finished:
			raise core.Error('line is already complete')

		self.finished = True
		self.variable = variable
		self.source = source


@dataclass
class Problem:
	message: str
	source: dap.SourceLocation

class Terminal:
	def __init__(self, name: str, cwd: str|None = None, file_regex: str|None = None):
		self.cwd = cwd
		self._name = name

		self.lines: list[Line] = []
		self.on_updated: core.Event[None] = core.Event()

		if file_regex:
			self.file_regex = re.compile(file_regex)
		else:
			self.file_regex = default_file_regex

		self.new_line = True
		self.escape_input = True
		self.finished = False
		self.statusCode = None
		self.statusMessage = None

	def name(self) -> str:
		return self._name

	def clicked_source(self, source: dap.SourceLocation) -> None:
		pass

	def _add_line(self, type: str, text: str, source: Optional[dap.SourceLocation] = None):
		if self.lines:
			previous = self.lines[-1]
			if not previous.finished and previous.type == type:
				previous.add(text, source, self.file_regex)
				return

		line = Line(type, self.cwd)
		line.add(text, source, self.file_regex)
		self.lines.append(line)
		self.on_updated.post()

	def add(self, type: str, text: str, source: Optional[dap.SourceLocation] = None):
		lines = text.splitlines(keepends=True)
		for line in lines:
			self._add_line(type, line, source)
			source = None

	def add_variable(self, variable: dap.Variable, source: Optional[dap.SourceLocation] = None):
		line = Line(None, None)
		line.add_variable(variable, source)
		self.lines.append(line)
		self.on_updated.post()

	def show_backing_panel(self):
		...

	def clear(self) -> None:
		self.lines = []
		self.on_updated()

	def writeable(self) -> bool:
		return False

	def can_escape_input(self) -> bool:
		return False

	def writeable_prompt(self) -> str:
		return ""

	def write(self, text: str) -> None:
		assert False, "Panel doesn't support writing"

	def dispose(self):
		pass

	def finish(self, status: int, message: str):
		self.finished = True
		self.statusCode = status
		self.statusMessage = message
		self.on_updated.post()

