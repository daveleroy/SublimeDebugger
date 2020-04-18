
import sublime
import Default #type: ignore

from ...import core
from .terminal import Terminal

class TerminalCommand(Terminal):
	def __init__(self, arguments: dict):
		arguments = arguments.copy()
		name = arguments.get('name')
		cmd = arguments.get('cmd')

		if (not name and isinstance(cmd, str)):
			name = cmd
		if (not name and isinstance(cmd, list)):
			name = cmd and cmd[0]
		if (not name):
			name = "Untitled"
		
		self.background = arguments.get('background', False)
		super().__init__(name)

		# if we don't remove these additional arguments Default.exec.ExecCommand will be unhappy
		if 'name' in arguments:
			del arguments['name']
		if 'background' in arguments:
			del arguments['background']

		self.exec = DebuggerExec(sublime.active_window(), self.write_stdout, arguments)

	def write_stdout(self, text: str):
		self.add('stdout', text)

	async def wait(self) -> None:
		await self.exec.wait()

id = 0
debugger_exec_for_id = {}

class DebuggerExec:
	def __init__(self, window: sublime.Window, on_output, args):
		global debugger_exec_for_id
		global id
		id += 1
		debugger_exec_for_id[id] = self

		self.future = core.create_future()
		self.on_output_callback = on_output

		window.run_command("debugger_exec", {
			"id": id,
			"args": args,
		})

		async def kill_if_canceled():
			try:
				await self.future
			except core.CancelledError as e:
				core.log_info("Cancel task")
				window.run_command("debugger_exec", {
					"id": id,
					"args": {
						"kill": True
					},
				})
				raise e
		core.run(kill_if_canceled())

	def on_kill(self):
		self.future.cancel()

	def on_output(self, characters):
		self.on_output_callback(characters)

	def on_finished(self, exit_code):
		if exit_code:
			self.future.set_exception(core.Error("Command failed with exit_code {}".format(exit_code)))
		else:
			self.future.set_result(None)

	async def wait(self) -> None:
		await self.future


class DebuggerExecCommand(Default.exec.ExecCommand):
	def run(self, id, args):
		self._id = id
		self.instance = debugger_exec_for_id[id]
		panel = self.window.active_panel()
		super().run(**args)

		# return to previous panel we don't want to show the build results panel
		self.window.run_command("show_panel", {"panel": panel})

	def kill(self):
		super().kill()
		self.instance.on_kill()

	# st3
	def finish(self, proc):
		super().finish(proc)
		self.instance.on_finished(proc.exit_code() or 0)

	# st3
	def append_string(self, proc, characters):
		super().append_string(proc, characters)
		self.instance.on_output(characters)

	# st4
	def on_finished(self, proc):
		super().on_finished(proc)
		self.instance.on_finished(proc.exit_code() or 0)

	# st4
	def write(self, characters):
		super().write(characters)
		self.instance.on_output(characters)

