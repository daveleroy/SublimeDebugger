from __future__ import annotations

import sublime

from .. import core
from ..command import Action, Section


class Start(Action):
	name = 'Start'
	key = 'start'

	# This command has a few modes
	# If a `configuration` argument is passed
	# Open or create the debugger
	# Start the debugger with the provided configuration

	# Otherwise
	# If there is no debugger create the debugger
	# If the debugger is not visible open the debugger
	# If the debugger is visibile start the debugger

	def action_raw(self, view, kwargs):
		from ..debugger import Debugger

		window = core.window_from_view_or_widow(view)
		if not window:
			return

		debugger = Debugger.get(window)
		existing_debugger = debugger

		if not debugger:
			if not window.project_file_name() and not len(kwargs):
				sublime.error_message('`Debugger: Open` requires a Sublime project')
				return

			debugger = Debugger.create(view)

		if not debugger.is_open():
			debugger.open()

		if existing_debugger or len(kwargs):
			debugger.start(args=kwargs)


class StartNoDebug(Action):
	name = 'Start (No Debug)'
	key = 'start_no_debug'

	def action(self, debugger):
		debugger.start(no_debug=True)


class Stop(Action):
	name = 'Stop'
	key = 'stop'

	def action(self, debugger):
		debugger.stop()

	def is_enabled(self, debugger):
		return debugger.is_stoppable()


class Continue(Action):
	name = 'Continue'
	key = 'continue'

	@core.run
	async def action(self, debugger):
		try:
			await debugger.current_session.resume()
		except core.Error as e:
			debugger.console.error(f'Unable to continue: {e}')

	def is_enabled(self, debugger):
		return debugger.is_paused()


class Pause(Action):
	name = 'Pause'
	key = 'pause'

	@core.run
	async def action(self, debugger):
		try:
			await debugger.current_session.pause()
		except core.Error as e:
			debugger.console.error(f'Unable to pause: {e}')

	def is_enabled(self, debugger):
		return debugger.is_running()


class StepOver(Action):
	name = 'Step Over'
	key = 'step_over'

	@core.run
	async def action(self, debugger):
		try:
			await debugger.current_session.step_over(granularity=debugger.stepping_granularity())
		except core.Error as e:
			debugger.console.error(f'Unable to step over: {e}')

	def is_enabled(self, debugger):
		return debugger.is_paused()


class StepIn(Action):
	name = 'Step In'
	key = 'step_in'

	@core.run
	async def action(self, debugger):
		try:
			await debugger.current_session.step_in(granularity=debugger.stepping_granularity())
		except core.Error as e:
			debugger.console.error(f'Unable to step in: {e}')

	def is_enabled(self, debugger):
		return debugger.is_paused()


class StepOut(Action):
	name = 'Step Out'
	key = 'step_out'

	@core.run
	async def action(self, debugger):
		try:
			await debugger.current_session.step_out(granularity=debugger.stepping_granularity())
		except core.Error as e:
			debugger.console.error(f'Unable to step out: {e}')

	def is_enabled(self, debugger):
		return debugger.is_paused()


Section()


class ReverseContinue(Action):
	name = 'Reverse Continue'
	key = 'reverse_continue'

	@core.run
	async def action(self, debugger):
		try:
			await debugger.current_session.reverse_continue()
		except core.Error as e:
			debugger.console.error(f'Unable to reverse continue: {e}')

	def is_enabled(self, debugger):
		return debugger.is_paused_and_reversable()


class StepBack(Action):
	name = 'Step Back'
	key = 'step_back'

	@core.run
	async def action(self, debugger):
		try:
			await debugger.current_session.step_back(granularity=debugger.stepping_granularity())
		except core.Error as e:
			debugger.console.error(f'Unable to step backwards: {e}')

	def is_enabled(self, debugger):
		return debugger.is_paused_and_reversable()
