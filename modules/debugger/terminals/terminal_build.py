
import sublime
import Default #type: ignore

from ...import core
from .terminal import Terminal



class TerminalBuild(Terminal):
	def __init__(self, arguments: dict):
		super().__init__('Build Results')
		self.future = run_build(sublime.active_window(), self.write_stdout, arguments)

	def write_stdout(self, text: str):
		self.add('stdout', text)

	@core.coroutine
	def wait(self) -> core.awaitable[int]:
		r = yield from self.future
		return r

on_finished_futures = {}
on_output_callbacks = {}
id = 0

@core.coroutine
def run_build(window: sublime.Window, on_output_callback, args) -> core.awaitable[int]:
	global on_finished_futures
	global id
	id += 1
	future = core.create_future()
	on_finished_futures[id] = future
	on_output_callbacks[id] = on_output_callback
	window.run_command("debugger_build_exec", {
		"id": id,
		"args": args,
	})

	try:
		exit_code = yield from future
		return exit_code

	except core.CancelledError as e:
		core.log_info("Cancel build")
		window.run_command("debugger_build_exec", {
			"id": id,
			"args": {
				"kill": True
			},
		})
		raise e


class DebuggerBuildExecCommand(Default.exec.ExecCommand):
	def run(self, id, args):
		self._id = id
		self.on_output_callback = on_output_callbacks[id]
		panel = self.window.active_panel()
		super().run(**args)
		print("run")
		self.window.run_command("show_panel", {"panel": panel})

	def finish(self, proc):
		print("run")
		super().finish(proc)
		future = self.future()
		if future:
			exit_code = proc.exit_code() or 0
			future.set_result(exit_code)

	def future(self):
		future = on_finished_futures.get(self._id)
		del on_finished_futures[self._id]
		return future

	def append_string(self, proc, str):
		super().append_string(proc, str)
		self.on_output_callback(str)

	def kill(self):
		print("kill")
		super().kill()
		future = self.future()
		if future:
			future.cancel()
