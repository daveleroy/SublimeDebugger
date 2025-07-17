from __future__ import annotations
from typing import Any
from os import name

from .dap.configuration import Input

from . import core
from . import ui
from . import dap
class SelectProcess(Input):
	async def resolve(self):
		try:
			import psutil
		except ImportError:
			raise dap.Error('Unable to select a process, `psutil` is not available')

		items: list[ui.InputListItem] = []
		selected_proc: Any = None

		def select(proc: Any):
			nonlocal selected_proc
			selected_proc = proc

		for proc in psutil.process_iter(['pid', 'name', 'username']):
			items.append(ui.InputListItem(lambda proc=proc: select(proc), proc.name() + f'\t{proc.pid}' + f'\t{proc.username()}'))

		await ui.InputList('Select a process to start debugging')[items]

		if selected_proc:
			return f'{selected_proc["pid"]}'

		raise core.CancelledError()
