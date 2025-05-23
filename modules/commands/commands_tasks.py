from __future__ import annotations
import functools
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from .. import dap
from .. import core
from .. import ui

from ..command import Action

if TYPE_CHECKING:
	from ..debugger import Debugger


class RunTask(Action):
	name = 'Run Task'
	key = 'run_task'

	last_run_task_name: WeakKeyDictionary[Debugger, str] = WeakKeyDictionary()

	@core.run
	async def action_with_args(self, debugger, **kwargs):
		select = kwargs.get('select') == True
		variables = debugger.project.extract_variables()
		last_run_task_name = self.last_run_task_name.get(debugger)

		tasks = list(debugger.project.tasks)
		for adapter in dap.Adapter.registered:
			tasks.extend(await adapter.tasks(variables))

		try:
			if not select and last_run_task_name:
				if matching_tasks := filter(lambda t: t.name == last_run_task_name, tasks):
					self.run_task(debugger, next(matching_tasks), variables)
				return

			values: list[ui.InputListItem] = []
			for task in tasks:
				values.append(ui.InputListItem(functools.partial(self.run_task, debugger, task, variables), task.name))

			ui.InputList('Select task to run')[values].run()

		except core.Error as e:
			debugger.console.error(f'{e}')

	@core.run
	async def run_task(self, debugger: Debugger, task: dap.Task, variables: dict[str, dap.Input]):
		self.last_run_task_name[debugger] = task.name
		debugger.dispose_terminals(unused_only=True)
		await debugger.tasks.run(debugger, await task.Expanded(variables))


class RunLastTask(Action):
	name = 'Select & Run Task'
	key = 'select_and_run_task'

	def action(self, debugger):
		debugger.window.run_command('debugger', {'action': 'run_task', 'args': {'select': True}})
