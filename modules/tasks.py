from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable

from . import core
from . import dap
from . import ui

from .output_panel_terminus import TerminusOutputPanel

if TYPE_CHECKING:
	from .debugger import Debugger

class Tasks(core.Dispose):
	def __init__(self) -> None:
		self.added = core.Event[TerminusOutputPanel]()
		self.removed = core.Event[TerminusOutputPanel]()
		self.updated = core.Event[TerminusOutputPanel]()
		self.tasks: list[TerminusOutputPanel] = []

	def is_active(self):
		for task in self.tasks:
			if not task.is_finished():
				return True
		return False

	@core.run
	async def run(self, debugger: Debugger, task: dap.TaskExpanded, is_terminal: bool = False):
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

		except dap.Error as error:
			raise dap.Error(f'Unable to resolve depends_on: {error}')

		terminal = TerminusOutputPanel(debugger, task, is_terminal)
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

	def on_options(self, task: TerminusOutputPanel):
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

	def cancel_background(self):
		for task in self.tasks:
			if task.task.background:
				task.kill_process()

		return False

	def cancel(self, task: TerminusOutputPanel):
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
