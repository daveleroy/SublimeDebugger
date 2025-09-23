from __future__ import annotations
from typing import TYPE_CHECKING
import sublime
import sublime_plugin

import re

from . import core
from . import dap
from . import ui

from .output_panel import OutputPanel

if TYPE_CHECKING:
	from .debugger import Debugger


class TerminusOutputPanel(OutputPanel):
	def __init__(self, debugger: Debugger, task: dap.TaskExpanded, is_terminal: bool = False):
		super().__init__(debugger, task.name, show_tabs=True)
		# title: str, cwd: str, commands: list[str], env: dict[str, str|None]|None
		self.future: core.Future[None] = core.Future()
		self.view.settings().add_on_change('debugger', self._on_settings_changed)

		# A terminal task generally never ends since it doesn't have a shell command
		self.is_terminal = is_terminal

		# title = task.name
		# cwd = task.get('working_dir')
		# commands = task.
		# is there a better way to do this? This could mean the user customized the settings but not have terminus installed?
		try:
			settings = sublime.load_settings('Terminus.sublime-settings')
			if not settings:
				raise dap.Error('Terminus must be installed to use the `console` value of `integratedTerminal`. Either install from Package control or change your debugging configuration `console` value to `integratedConsole`.')

			self.task = task
			core.edit(self.view, lambda edit: self.view.insert(edit, 0, ''))

			arguments = task.copy()

			# if we don't remove these additional arguments Default.exec.ExecCommand will be unhappy
			for key in ['name', 'background', 'start_file_regex', 'end_file_regex', 'depends_on', 'depends_on_order', 'ready_signal_pattern', 'ready_signal_timeout']:
				if key in arguments:
					del arguments[key]

			try:
				self.verify_arguments(**arguments)
			except TypeError as e:
				message: str = e.args[0]
				if message.startswith('verify_arguments() got an unexpected keyword argument '):
					message = message.replace('verify_arguments() got an unexpected keyword argument ', '')
					raise dap.Error('Terminus: unknown key in task ' + message)

				core.error('Unable to start Terminus', e)
				raise dap.Error(str(e))

			arguments['tag'] = self.output_panel_name
			arguments['panel_name'] = self.panel_name
			arguments['auto_close'] = False
			arguments['post_view_hooks'] = [
				['debugger_terminus_post_view_hooks', {}],
			]

			debugger.window.run_command('terminus_open', arguments)

			# if self.task.start_file_regex or self.task.end_file_regex:
			# 	self.attach(self.view.buffer())

			self.set_status(ui.Images.shared.loading)

		except dap.Error as error:
			self.throw(error)

	@core.run
	async def throw(self, error: dap.Error):
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
				self.future.set_exception(dap.Error(line))
				self.set_status(ui.Images.shared.clear)

		elif match := re.match(r'\[Finished in (.*)s\]', line):
			self.future.set_result(None)
			self.set_status(ui.Images.shared.check_mark)

		elif match := re.match(r'\[Finished in (.*)s with exit code (.*)\]', line):
			self.future.set_exception(dap.Error(line))
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

	def cancel(self):
		"""Actually cancel/kill the running background process"""
		if not self.is_finished():
			# Use terminus_cancel_build to actually kill the running process
			# (terminus_cancel only closes UI, doesn't kill the process)
			self.view.run_command('terminus_cancel_build')
			# Set as cancelled if the future isn't done yet
			if not self.future.done():
				self.future.set_exception(core.CancelledError)

	def dispose(self):
		super().dispose()
		self.view.run_command('terminus_close')


class DebuggerTerminusPostViewHooks(sublime_plugin.TextCommand):
	def run(self, edit: sublime.Edit): #type: ignore
		settings = self.view.settings()
		settings.set('scroll_past_end', False)
		settings.set('scroll_past_end', False)
		settings.set('word_wrap', True)
		settings.set('draw_unicode_white_space', 'none')
