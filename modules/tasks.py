from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable

import asyncio
import re
import time
import sublime

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

		# For background tasks with a ready signal pattern, wait for it before returning
		if task.background and task.ready_signal_pattern is not None:
			debugger.console.info(f"Waiting for '{task.name}' to be ready...")
			try:
				await self.wait_for_ready_signal_with_timeout(terminal, task.ready_signal_pattern, task.ready_signal_timeout, debugger)
				debugger.console.info(f"Task '{task.name}' is ready")
			except asyncio.TimeoutError:
				debugger.console.info(f"Timeout waiting for task '{task.name}'")
			except Exception as e:
				debugger.console.error(f"Error waiting for task '{task.name}': {e}")
		elif not task.background:
			# For non-background tasks, wait for completion
			await terminal.wait()
		
		# Return the terminal so it can be tracked for cleanup
		return terminal

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

	def cancel(self, task: TerminusOutputPanel):
		try:
			self.tasks.remove(task)
		except ValueError:
			return

		# Actually cancel the running background process
		task.cancel()
		self.removed(task)
		task.dispose()

	async def wait_for_ready_signal_with_timeout(self, terminal: TerminusOutputPanel, pattern: str, timeout: float, debugger: Debugger) -> None:
		"""
		Wait for a regex pattern to appear in the task output with a timeout.
		This is useful for background tasks that need to signal when they're ready.
		"""
		compiled_pattern = re.compile(pattern)
		check_count = 0
		start_time = time.time()
		
		while not terminal.is_finished():
			# Check if we've exceeded the timeout
			elapsed = time.time() - start_time
			if elapsed > timeout:
				raise asyncio.TimeoutError(f"Timeout waiting for pattern '{pattern}'")
			
			# Get the current content of the output view
			content = terminal.view.substr(sublime.Region(0, terminal.view.size()))
			check_count += 1
			
			# Check if the pattern matches
			if compiled_pattern.search(content):
				return
			
			await core.delay(0.1)
		
		# If task finished without matching the pattern
		raise Exception(f"Task finished without matching pattern '{pattern}'")

	def dispose(self):
		while self.tasks:
			task = self.tasks.pop()
			self.removed(task)
			task.dispose()
