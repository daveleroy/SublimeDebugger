from __future__ import annotations
from typing import Callable

from ..import ui
from ..import dap
from ..import core

from .import css

import os
from functools import partial

from .tabbed_panel import Panel
from ..terminal_task import Tasks, TerminalTask, Diagnostics, Diagnostic

class DiagnosticsPanel (Panel):
	def __init__(self, tasks: Tasks, on_clicked_source: Callable[[dap.SourceLocation], None]) -> None:
		super().__init__('Problems')
		self.on_clicked_source = on_clicked_source
		self.diagnostics_per_file: list[Diagnostics] = []
		self.collapsed_files: set[str] = set()
		self.tasks = tasks
		self.diagnostic_count = 0

		self.tasks.added.add(lambda _: self.dirty())
		self.tasks.updated.add(lambda _: self.dirty())
		self.tasks.removed.add(lambda _: self.dirty())
		
		self.timer = None

	def visible(self):
		return self.diagnostic_count != 0 or len(self.tasks.tasks) != 0

	def panel_header(self, expanded: bool) -> list[ui.span] | None:
		if self.diagnostic_count == 0:
			return [
				ui.spacer(1),
				ui.text(self.name, css=css.label_secondary),
				ui.spacer(2),
			]

		return [
			ui.text(self.name, css=css.label_secondary),
			ui.spacer(1),
			badge(str(self.diagnostic_count)),
		]

	def dirty(self):
		self.dirty_header()
		super().dirty()


	def update(self, id: str, diagnostics_per_file: list[Diagnostics]):
		self.diagnostics_per_file = diagnostics_per_file
		self.diagnostic_count = 0

		for diagnostics in self.diagnostics_per_file:
			self.diagnostic_count += len(diagnostics['errors'])

		def dirty():
			self.dirty()
			self.timer = None

		if self.timer == None:
			self.timer = core.call_later(0.5, dirty)


	def on_clicked(self, file: str, problem: Diagnostic):
		if problem:
			line = problem['range']['start']['line']
			column = problem['range']['start'].get('character') or 0
			source = dap.SourceLocation.from_path(file, line + 1, column + 1)
		else:
			source = dap.SourceLocation.from_path(file, None, None)

		self.on_clicked_source(source)

	def toggle_expanded(self, file: str):
		if file in self.collapsed_files:
			self.collapsed_files.remove(file)
		else:
			self.collapsed_files.add(file)

		self.dirty()

	def render(self):
		items: list[ui.div] = []
		

		def toggle(diagnostics: Diagnostics):
			self.toggle_expanded(diagnostics['file'])

		def on_clicked(diagnostics: Diagnostics, diagnostic: Diagnostic):
			self.on_clicked(diagnostics['file'], diagnostic)

		def on_clicked_task(task: TerminalTask):

			def cancel():
				self.tasks.cancel(task)

			def show_panel():
				task.show_backing_panel()

			ui.InputList([
				ui.InputListItem(show_panel, 'Show Output'),
				ui.InputListItem(cancel, 'Clear' if task.finished else 'Cancel'),
			]).run()

		for task in self.tasks.tasks:
			items.append(TaskView(self.tasks, task, on_clicked_task))

			for diagnostics in task.diagnostics_per_file:
				items.append(DiagnosticsView(diagnostics, diagnostics['file'] in self.collapsed_files, on_toggle=toggle, on_clicked_diagnostic=on_clicked))


		for diagnostics in self.diagnostics_per_file:
			items.append(DiagnosticsView(diagnostics, diagnostics['file'] in self.collapsed_files, on_toggle=toggle, on_clicked_diagnostic=on_clicked))

		return items

def CloseButton(toggle: Callable[[], None]) -> ui.span:
	return ui.click(toggle)[
		ui.span(css=css.button)[
			ui.text('X', css=css.label)
		]
	]

def TaskView(tasks: Tasks, task: TerminalTask, on_clicked: Callable[[TerminalTask], None]):
	if not task.finished:
		text = 'Running'
		color = css.label_greenish

	elif task.exit_code is None:
		text = 'Cancelled'
		color = css.label_redish

	elif task.exit_code == 0:
		text = 'Finished'
		color = css.label_bluish
	else:
		text = 'Failed'
		color = css.label_redish

	def show():
		task.show_backing_panel()

	def cancel():
		tasks.cancel(task)

	def input():
		ui.InputList([
			ui.InputListItem(show, 'Show Output'),
			ui.InputListItem(cancel, 'Clear' if task.finished else 'Cancel'),
		]).run()

	return ui.div(height=css.row_height)[
		ui.click(input)[
			ui.align()[
				ui.span(css=css.button)[
					ui.text(text, css=color)
				],
				ui.spacer(1),
				ui.text(task.name, css=css.label),
				ui.spacer(min=1),
				ui.click(cancel)[
					ui.text(text='×', css=css.button_secondary),
				],
				ui.spacer(1),
				ui.click(show)[
					ui.text(text='↗', css=css.button_secondary)
				]
			]
		]
	]

def DiagnosticsView(diagnostics: Diagnostics, collapsed: bool, on_toggle: Callable[[Diagnostics], None], on_clicked_diagnostic: Callable[[Diagnostics, Diagnostic], None]) -> ui.div:
	items: list[ui.div] = []

	file: str = diagnostics['file']
	base: str|None = diagnostics.get('base')
	errors: list[Diagnostic] = diagnostics['errors']


	is_expanded = not collapsed

	file_rel: str = os.path.relpath(file, base) if base else file

	items.append(ui.div(height=css.row_height)[
		ui.click(partial(on_toggle, diagnostics)) [
			ui.align()[
				toggle(is_expanded),
				file_span(file_rel),
			]
		],
	])

	if not is_expanded:
		return ui.div()[
			items
		]

	errors.sort(key=lambda a: a['range']['start']['line'])

	for problem in errors:
		severity = problem['severity']
		if severity == 1:
			error_or_warning = ui.text('error', css=css.label_redish)
		elif severity == 2:
			error_or_warning = ui.text('warning', css=css.label_yellowish)
		else:
			error_or_warning = ui.text('info', css=css.label_bluish)

		item = ui.div(height=css.row_height)[
			ui.click(partial(on_clicked_diagnostic, diagnostics, problem))[
				ui.align()[
					ui.spacer(3),
					ui.span(css=css.button)[
						error_or_warning
					],
					ui.spacer(1),
					ui.text(problem['message'], css=css.label_secondary),
					ui.spacer(min=1),
					ui.span(css=css.button)[
						ui.text(str(problem['range']['start']['line']+1), css=css.label)
					]
				]
			]
		]
		items.append(item)

	return ui.div()[
		items
	]

badge_css = ui.css(
	padding_left=0.5,
	padding_right=0.5,
	padding_top=-0.3,
	padding_bottom=-0.3,
	background_color='color(var(--secondary) alpha(0.1)',
	raw='border-radius: 0.65rem;'
)


def file_span(file: str) -> ui.span:
	folder, name = os.path.split(file)
	if folder:
		return ui.span()[
			ui.text(name, css=css.label),
			ui.spacer(1),
			ui.text(folder, css=css.label_secondary),
		]
	return ui.text(name, css=css.label)

def badge(value: str):
	return ui.span(css=badge_css)[
		ui.text(value, css=css.label)
	]

def toggle(is_expanded: bool):
	# return ui.text('▾ ', css=css.label_placeholder) if is_expanded else ui.text('▸ ', css=css.label_placeholder) 
	# return ui.text('▼ ', css=css.label_placeholder) if is_expanded else ui.text('▶ ', css=css.label_placeholder) 
	return ui.icon(ui.Images.shared.open if is_expanded else ui.Images.shared.close)
						