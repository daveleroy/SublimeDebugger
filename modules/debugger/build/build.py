
import sublime
import Default

from ... import core

on_finished_futures = {}
on_output_callbacks = {}
id = 0

@core.coroutine
def run(window: sublime.Window, on_output_callback, args) -> core.awaitable[None]:
	global on_finished_futures
	global id
	id += 1
	future = core.create_future()
	on_finished_futures[id] = future
	on_output_callbacks[id] = on_output_callback
	print(args)
	window.run_command("debugger_build_exec", {
		"id": id, 
		"args": args,
	})
	return future

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
			future.set_result(None)

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

