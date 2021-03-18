from __future__ import annotations
from .typecheck import *

from .import core
from .import ui

import sublime
import re


@core.schedule
async def select_process():
	from .libs import psutil

	items: list[ui.InputListItem] = []
	selected_proc: Any = None

	def select(proc: Any):
		nonlocal selected_proc
		selected_proc = proc

	for proc in psutil.process_iter(['pid', 'name', 'username']):
		items.append(ui.InputListItem(lambda proc=proc: select(proc), proc.name() + f'\t{proc.pid}'+ f'\t{proc.username()}'))

	await ui.InputList(items, "Select a process to start debugging").run()

	if selected_proc:
		return selected_proc.pid

	raise core.Error("No process selected")