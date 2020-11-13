from typing import Dict, Any, List

import re
import sublime
import Default #type: ignore
import time

from ... import core
from .. import dap

from .terminal import Terminal, Problem
from ..panel import OutputPanel

problem_matchers = {
	'$cc': '(..[^:]*):([0-9]+):([0-9]+)?:? error: (.*)',
	'$ccc': '(..[^:]*):([0-9]+):([0-9]+)?:? error: (.*)',
}

class TerminalTask(Terminal):
	def __init__(self, window: sublime.Window, task: dap.TaskExpanded):

		arguments = task.copy()
		name = arguments.get('name')
		cmd = arguments.get('cmd')

		if not name and isinstance(cmd, str):
			name = cmd
		if not name and isinstance(cmd, list):
			name = cmd and cmd[0]
		if not name:
			name = "Untitled"

		self.background = arguments.get('background', False)

		super().__init__(name, arguments.get('working_dir'), arguments.get('file_regex'))

		# if we don't remove these additional arguments Default.exec.ExecCommand will be unhappy
		if 'name' in arguments:
			del arguments['name']
		if 'background' in arguments:
			del arguments['background']


		self.on_problems_updated: core.Event[None] = core.Event()
		self.problems_per_file: Dict[str, List[Problem]] = {}

		self.future = core.create_future()
		self.window = window

		# only save the views that have an assigned file
		for view in self.window.views():
			if view.file_name() and view.is_dirty():
				view.run_command('save')

		self.panel = OutputPanel(self.window, name, show_panel=False)

		self.command = Exec(self.window)
		self.command.output_view = self.panel.view
		self.command.run(self, arguments)

		self.on_view_load_listener = core.on_view_load.add(self.on_view_load)

	def show_backing_panel(self):
		self.panel.open()

	def on_view_load(self, view: sublime.View):
		# refresh the phantoms from exec
		self.command.update_phantoms()

	def dispose(self):
		self.on_view_load_listener.dispose()
		self.panel.dispose()

	def write_stdout(self, text: str):
		self.add('terminal.output', text)

	async def wait(self) -> None:
		try:
			await self.future
		except core.CancelledError as e:
			print(f'Command cancelled {self.name()}')
			self.command.run(self, {
				'kill': True
			})
			raise e

	def on_output(self, characters):
		self.write_stdout(characters)

	def on_updated_errors(self, errors_by_file):
		self.problems_per_file.clear()
		for file, errors in errors_by_file.items():
			problems = []
			for error in errors:
				problems.append(Problem(error[2], dap.SourceLocation.from_path(file, error[0], error[1])))

			self.problems_per_file[file] = problems

		self.on_problems_updated()

	def on_finished(self, exit_code):
		self.finished = True

		if self.future.done():
			return

		if exit_code:
			self.future.set_exception(core.Error(f'Command {self.name()} failed with exit_code {exit_code}'))
		else:
			self.future.set_result(None)

		self.on_updated()


class Exec(Default.exec.ExecCommand):
	def run(self, instance, args):
		if 'problem_matcher' in args:
			print(args['problem_matcher'])
			args['file_regex'] = problem_matchers.get(args['problem_matcher'], args['problem_matcher'])
			del args['problem_matcher']

		self.instance = instance
		panel = self.window.active_panel()
		super().run(**args)

		# return to previous panel we don't want to show the build results panel
		self.window.run_command("show_panel", {"panel": panel})

	def update_phantoms(self):
		super().update_annotations()

	def update_annotations(self):
		super().update_annotations()
		self.instance.on_updated_errors(self.errs_by_file)

	def on_finished(self, proc):
		super().on_finished(proc)

		# modified from Default exec.py
		if self.instance:
			if proc.killed:
				self.instance.statusMessage = "[Cancelled]"
			else:
				elapsed = time.time() - proc.start_time
				exit_code = proc.exit_code()
				if exit_code == 0 or exit_code is None:
					self.instance.statusCode = 0
					self.instance.statusMessage = "[Finished in %.1fs]" % elapsed
				else:
					self.instance.statusCode = exit_code
					self.instance.statusMessage = "[Finished in %.1fs with exit code %d]" % (elapsed, exit_code)

			self.instance.on_finished(proc.exit_code() or 0)
			# self.window.run_command("next_result")

	def write(self, characters):
		super().write(characters)
		self.instance.on_output(characters)

