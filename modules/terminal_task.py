from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, Callable


import sublime
import Default #type: ignore
import time
import sys
import re

from .import core
from .import dap
from .import ui

from .ansi import ansi_colorize
from .debugger_output_panel import DebuggerOutputPanel

if TYPE_CHECKING:
	from .debugger import Debugger

@dataclass
class Problem:
	message: str
	source: dap.SourceLocation

class Position(TypedDict):
	line: int
	character: int|None

class Range(TypedDict):
	start: Position

class Diagnostic(TypedDict):
	range: Range
	severity: int
	message: str

class Diagnostics(TypedDict):
	file: str
	base: str|None
	errors: list[Diagnostic]

class TerminalTask(DebuggerOutputPanel):

	on_ended_event: core.Event[None]

	# tasks can "finish" but still be running. For instance background tasks continue to run in the background but are finished right away
	on_finished_event: core.Event[None]

	on_options: Callable[[], None]|None = None

	def __init__(self, debugger: Debugger, task: dap.TaskExpanded):
		self.on_updated = core.Event()
		self.on_ended_event = core.Event()
		self.on_finished_event = core.Event()
		self.task = task
		super().__init__(debugger, task.name)

		self.finished = False

		self.on_problems_updated: core.Event[None] = core.Event()
		self.diagnostics_per_file: list[Diagnostics] = []

		self.future: core.Future[None] = core.Future()

		# only save the views that have an assigned file
		for view in self.window.views():
			if view.file_name() and view.is_dirty():
				view.run_command('save')

		self.exec = Default.exec.ExecCommand(self.window)
		self.exec.output_view = self.view

		self.exec_update_annotations = self.exec.update_annotations

		self._exec_on_finished_original = self.exec.on_finished
		self.exec.on_finished = self._exec_on_finished


		self._exec_write = self.exec.write
		self.exec.write = self.write

		self.view.set_viewport_position((0, sys.maxsize), False)
		self.on_view_load_listener = core.on_view_load.add(self.on_view_load)

		self.set_status(ui.Images.shared.loading)

		def run():
			self.exec.run(**arguments)
			self.view.assign_syntax('Packages/Debugger/Commands/DebuggerConsole.sublime-syntax')
			self.open()

		sublime.set_timeout(run, 0)


	def write(self, characters: str):
		self._exec_write(ansi_colorize(characters))

	def open_status(self):
		if on_options := self.on_options:
			on_options()

	def show_backing_panel(self):
		self.open()

	def on_view_load(self, view: sublime.View):
		# refresh the phantoms from exec
		self.exec.update_annotations()

	def dispose(self):
		super().dispose()

		try:
			self.exec.proc.kill()
		except ProcessLookupError: 
			...
		except Exception as e:
			core.exception(e)

		self.exec.hide_annotations()
		self.on_view_load_listener.dispose()

	async def wait(self) -> None:
		try:
			await self.future
		except core.CancelledError as e:
			print(f'Command cancelled {self.name}')
			self.exec.run(kill=True)
			raise e

	def cancel(self) -> None:
		self.exec.run(kill=True)

	def on_updated_errors(self, errors_by_file):
		self.diagnostics_per_file.clear()

		for file, errors in errors_by_file.items():
			diagnostics: list[Diagnostic] = []
			for error in errors:
				diagnostic: Diagnostic = {
					'severity': 1,
					'message': error[2],
					'range': {
						'start': {
							'line': error[0],
							'character': error[1]
						}
					}
				}
				diagnostics.append(diagnostic)

			self.diagnostics_per_file.append({
				'file': file,
				'base': None,
				'errors': diagnostics
			})

		self.on_problems_updated.post()

	def _exec_on_finished(self, proc):
		self._exec_on_finished_original(proc)

		if proc.killed:
			exit_status = "[Cancelled]"
			exit_code: int|None = None
		else:
			elapsed = time.time() - proc.start_time
			exit_code: int|None = proc.exit_code() or 0
			if exit_code == 0:
				exit_status = "[Finished in %.1fs]" % elapsed
			else:
				exit_status = "[Finished in %.1fs with exit code %d]" % (elapsed, exit_code)


		if self.finished:
			return

		self.finished = True
		self.exit_code = exit_code
		self.exit_status = exit_status

		if exit_code is None:
			self.future.cancel()
			self.set_status(ui.Images.shared.clear)
		elif exit_code == 0:
			self.future.set_result(None)
			self.set_status(ui.Images.shared.check_mark)
		else:
			self.set_status(ui.Images.shared.clear)
			self.future.set_exception(core.Error(f'`{self.name}` failed with exit_code {exit_code}'))


class TerminusTask(DebuggerOutputPanel):
	def __init__(self, debugger: Debugger, task: dap.TaskExpanded):

		# title: str, cwd: str, commands: list[str], env: dict[str, str|None]|None

		# title = task.name
		# cwd = task.get('working_dir')
		# commands = task.

		# is there a better way to do this? This could mean the user customized the settings but not have terminus installed?
		settings = sublime.load_settings("Terminus.sublime-settings")
		if not settings:
			raise core.Error('Terminus must be installed to use the `console` value of `integratedTerminal`. Either install from Package control or change your debugging configuration `console` value to `integratedConsole`.')

		super().__init__(debugger, task.name, show_tabs=True)

		self.task = task
		core.edit(self.view, lambda edit: self.view.insert(edit, 0, ''))

		arguments = task.copy()
		arguments['tag' ] = self.output_panel_name
		arguments['panel_name'] = self.name
		arguments['auto_close'] = False
		arguments['post_view_hooks'] = [
			['debugger_terminus_post_view_hooks', {}],
		]
		debugger.window.run_command('terminus_open', arguments)
		

		self.future: core.Future[None] = core.Future()
		self.view.settings().add_on_change('debugger', self._on_settings_changed)

		self.set_status(ui.Images.shared.loading)

	def _check_status_code(self):
		if self.future.done():
			return

		line = self.view.substr(self.view.full_line(self.view.size()))
		if match := re.match(r'process is terminated with return code (.*)\.', line):
			if match[1] == '0':
				self.future.set_result(None)
				self.set_status(ui.Images.shared.check_mark)
			else:
				self.future.set_exception(core.Error(line))
				self.set_status(ui.Images.shared.clear)

		elif match := re.match(r'\[Finished in (.*)s\]', line):
			self.future.set_result(None)
			self.set_status(ui.Images.shared.check_mark)

		elif match := re.match(r'\[Finished in (.*)s with exit code (.*)\]', line):
			self.future.set_exception(core.Error(line))
			self.set_status(ui.Images.shared.clear)

		else:
			self.future.set_exception(core.CancelledError)
			self.set_status(ui.Images.shared.clear)

	def _on_settings_changed(self):
		if self.future.done() or not self.is_finished():
			return
		
		# terminus marks the terminal as finished before adding the status line
		sublime.set_timeout(self._check_status_code, 0)

	async def wait(self):
		await self.future

	def is_finished(self):
		return self.view.settings().get('terminus_view.finished')

	def cancel(self): ...

	def dispose(self):
		super().dispose()
		self.view.run_command('terminus_close')


class TaskRunner(Protocol):
	task: dap.TaskExpanded

	async def wait(self) -> None: ...
	def is_finished(self): ...
	def dispose(self): ...
	def cancel(self): ...


class Tasks:
	tasks: list[TaskRunner]

	added: core.Event[TaskRunner]
	removed: core.Event[TaskRunner]
	updated: core.Event[TaskRunner]

	def __init__(self) -> None:
		self.added = core.Event()
		self.removed = core.Event()
		self.updated = core.Event()
		self.tasks = []

	def is_active(self):
		for task in self.tasks:
			if not task.is_finished():
				return True
		return False

	@core.schedule
	async def run(self, debugger: Debugger, task: dap.TaskExpanded):

		# if there is already an existing task we wait on it to finish and do not start a new task
		# this matches the behavior of vscode?
		for t in self.tasks:
			if t.task.name == task.name and not t.is_finished():
				debugger.on_info('This task has already been started')
				if not t.task.background:
					await t.wait()
				return


		terminal = TerminusTask(debugger, task)
		terminal.on_opened_status = lambda: self.on_options(terminal)

		self.tasks.append(terminal)
		self.added(terminal)

		@core.schedule
		async def update_when_done():
			try:
				await terminal.wait()
			except:
				raise
			finally:
				self.updated(terminal)

		update_when_done()

		if not task.background:
			await terminal.wait()

	def on_options(self, task: TaskRunner):
		if task.is_finished():
			self.cancel(task)
			return

		options = ui.InputList([
			ui.InputListItem(lambda: self.cancel(task), 'Kill Task'),
		])
		options.run()

	def remove_finished(self):
		remove_tasks = []
		for task in self.tasks:
			if task.is_finished():
				remove_tasks.append(task)

		for task in remove_tasks:
			self.cancel(task)

		return False

	def cancel(self, task: TaskRunner):
		try:
			self.tasks.remove(task)
		except ValueError:
			return
			
		# todo actually cancel...
		self.removed(task)
		task.dispose()

	def dispose(self):
		while self.tasks:
			task = self.tasks.pop()
			self.removed(task)
			task.dispose()

