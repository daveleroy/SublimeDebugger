from __future__ import annotations
import functools
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from ...modules.output_panel import OutputPanel
from ...modules.output_panel_terminus import TerminusOutputPanel
import sublime

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
				values.append(ui.InputListItem(functools.partial(self.run_task, debugger, task, variables), task.name, run_alt=lambda task=task: task.source and task.source.open_file()))

			ui.InputList('Select task to run')[values].run()

		except dap.Error as e:
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
		debugger.window.run_command('debugger', {'action': 'run_task', 'select': True})


class NewTerminal(Action):
	name = 'New Terminal'
	key = 'new_terminal'

	@core.run
	async def action(self, debugger: Debugger):
		debugger.dispose_terminals(unused_only=True)

		for task in debugger.tasks.tasks:
			if task.task.name == 'Terminal':
				await ui.InputText(
					lambda name: self.create(debugger, name),
					'Create New Terminal With Name',
				)
				return

		await self.create(debugger, 'Terminal')

	@core.run
	async def create(self, debugger: Debugger, name: str):
		task = await dap.Task({'name': name}).Expanded({})
		await debugger.tasks.run(debugger, task, is_terminal=True)


class OpenTerminal(Action):
	name = 'Open Terminal'
	key = 'open_terminal'

	@core.run
	async def action(self, debugger: Debugger):
		found_terminal = False

		panels:list[OutputPanel] = debugger.tasks.get_panels()

		for i, panel in enumerate(panels):
			found_terminal = found_terminal or (panel is TerminusOutputPanel and panel.is_terminal)

		if not found_terminal:
			debugger.run_action(NewTerminal)
			return

		# Otherwise cyncle through all the active console like items
		next_panel = 0

		# cycle through active terminal like panels
		if debugger.session:
			panels.insert(0, debugger.console)

		for i, panel in enumerate(panels):
			if panel.is_open():
				next_panel = i + 1
				break

		next_panel = panels[next_panel % len(panels)]
		next_panel.open()


class CancelTasks(Action):
	name = 'Cancel All Tasks'
	key = 'cancel_all_tasks'

	is_menu_commands = False
	is_menu_main = False

	@core.run
	async def action_with_args(self, debugger, **kwargs):
		running_tasks = debugger.tasks.get_running()
		for task in running_tasks:
			task.cancel()


class CancelTask(Action):
	name = 'Cancel Task'
	key = 'cancel_task'

	@core.run
	async def action_with_args(self, debugger, **kwargs):
		name: str | list[str] | None = kwargs.get('name')

		running_tasks = debugger.tasks.get_running()

		if name is not None:
			task_names = [name] if name is str else name
			for task in running_tasks:
				if task.task.name in task_names:
					task.cancel()
			return


		values: list[ui.InputListItem] = []

		# todo? re-run cancel_task with the name field set so that this extra case shows up in the sublime console when log_commands is true which makes commands easier to find
		for task in running_tasks:
			values.append(ui.InputListItem(functools.partial(self.cancel_task, debugger, task.task), task.task.name, run_alt=lambda task=task: task.source and task.source.open_file()))

		await ui.InputList('Select task to cancel')[values].run()

	@core.run
	async def cancel_task(self, debugger: Debugger, task: dap.Task):
		running_tasks = debugger.tasks.get_running()
		if matching_tasks := filter(lambda t: t.task == task, running_tasks):
			next(matching_tasks).cancel()
