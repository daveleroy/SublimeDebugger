from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable, Protocol

import sublime
import re

from . import core
from . import dap
from . import ui

from .output_panel import OutputPanel

if TYPE_CHECKING:
	from .debugger import Debugger


class Tasks(core.Dispose):
	def __init__(self) -> None:
		self.added = core.Event[TerminusTask]()
		self.removed = core.Event[TerminusTask]()
		self.updated = core.Event[TerminusTask]()
		self.tasks: list[TerminusTask] = []

	def is_active(self):
		for task in self.tasks:
			if not task.is_finished():
				return True
		return False

	@core.run
	async def run(self, debugger: Debugger, task: dap.TaskExpanded):
		# if there is already an existing task we wait on it to finish and do not start a new task
		# this matches the behavior of vscode?
		for t in self.tasks:
			if t.task.name == task.name and not t.is_finished():
				debugger.console.info('This task has already been started')
				if not t.task.background:
					await t.wait()
				return

		depends_on = task.depends_on
		sequence = task.depends_on_order == 'sequence'

		if isinstance(depends_on, str):
			depends_on = [depends_on]
		elif isinstance(depends_on, list):
			depends_on = depends_on
		else:
			depends_on = []

		try:
			if sequence:
				for depends_on_name in depends_on:
					depends_on_task = debugger.project.get_task(depends_on_name)
					depends_on_task_expanded = await depends_on_task.Expanded(task.variables)
					await self.run(debugger, depends_on_task_expanded)

			else:
				depends_on_tasks_expanded: list[Awaitable[None]] = []
				for depends_on_name in depends_on:
					depends_on_task = debugger.project.get_task(depends_on_name)
					depends_on_task_expanded = await depends_on_task.Expanded(task.variables)
					depends_on_tasks_expanded.append(self.run(debugger, depends_on_task_expanded))

				await core.gather(*depends_on_tasks_expanded)

		except core.Error as error:
			raise core.Error(f'Unable to resolve depends_on: {error}')

		terminal = TerminusTask(debugger, task)
		terminal.on_opened_status = lambda: self.on_options(terminal)

		self.tasks.append(terminal)
		self.added(terminal)

		@core.run
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

	def on_options(self, task: TerminusTask):
		if task.is_finished():
			self.cancel(task)
			return

		options = ui.InputList('Kill task?')[ui.InputListItem(lambda: self.cancel(task), 'Kill'),]
		options.run()

	def remove_finished(self):
		remove_tasks = []
		for task in self.tasks:
			if task.is_finished():
				remove_tasks.append(task)

		for task in remove_tasks:
			self.cancel(task)

		return False

	def cancel(self, task: TerminusTask):
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


class TerminusTask(OutputPanel):
	def __init__(self, debugger: Debugger, task: dap.TaskExpanded):
		super().__init__(debugger, task.name, show_tabs=True)
		# title: str, cwd: str, commands: list[str], env: dict[str, str|None]|None
		self.future: core.Future[None] = core.Future()
		self.view.settings().add_on_change('debugger', self._on_settings_changed)

		# is there a better way to do this? This could mean the user customized the settings but not have terminus installed?
		try:
			settings = sublime.load_settings('Terminus.sublime-settings')
			if not settings:
				raise core.Error('Terminus must be installed to use the `console` value of `integratedTerminal`. Either install from Package control or change your debugging configuration `console` value to `integratedConsole`.')

			self.task = task
			core.edit(self.view, lambda edit: self.view.insert(edit, 0, ''))

			arguments = task.copy()
			arguments['tag'] = self.output_panel_name
			arguments['panel_name'] = self.panel_name
			arguments['auto_close'] = False
			arguments['post_view_hooks'] = [
				['debugger_terminus_post_view_hooks', {}],
			]
			try:
				self.verify_arguments(**arguments)
			except TypeError as e:
				message: str = e.args[0]
				if message.startswith('verify_arguments() got an unexpected keyword argument '):
					message = message.replace('verify_arguments() got an unexpected keyword argument ', '')
					raise core.Error('Terminus: unknown key in task ' + message)

				core.error('Unable to start Terminus', e)
				raise core.Error(str(e))

			debugger.window.run_command('terminus_open', arguments)

			# if self.task.start_file_regex or self.task.end_file_regex:
			# 	self.attach(self.view.buffer())

			self.set_status(ui.Images.shared.loading)

		except core.Error as error:
			self.throw(error)

	@core.run
	async def throw(self, error: core.Error):
		# just in case an error happens instantly there will be a flash when retrying
		await core.delay(0.05)

		text = str(error)
		core.edit(self.view, lambda e: self.view.insert(e, 0, text))
		self.set_status(ui.Images.shared.clear)
		self.future.set_exception(error)

	def verify_arguments(
		self,
		config_name=None,
		cmd=None,
		shell_cmd=None,
		cwd=None,
		working_dir=None,
		env={},
		title=None,
		show_in_panel=None,
		panel_name=None,
		focus=True,
		tag=None,
		file_regex=None,
		line_regex=None,
		pre_window_hooks=[],
		post_window_hooks=[],
		post_view_hooks=[],
		view_settings={},
		auto_close=True,
		cancellable=False,
		reactivable=True,
		timeit=False,
		paths=[],
	): ...


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
		return self.view.settings().get('terminus_view.finished') or self.future.done()

	def cancel(self): ...

	def dispose(self):
		super().dispose()
		self.view.run_command('terminus_close')
