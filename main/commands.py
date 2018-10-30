import sublime_plugin
import sublime

from sublime_db import core

from sublime_db.main.main import Main
from sublime_db.main.debug_adapter_client.client import DebuggerState, DebugAdapterClient
from sublime_db.main.configurations import get_setting

def DebuggerInState(window: sublime.Window, state: int) -> bool:
	debugger = Main.debuggerForWindow(window)
	if debugger and debugger.state == state:
		return True
	return False

class RunMainCommand(sublime_plugin.WindowCommand):
	def run(self) -> None:
		core.main_loop.call_soon_threadsafe(self.run_main)
	def run_main (self) -> None:
		pass

class DebugWindowCommand(RunMainCommand):
	def is_visible(self) -> bool:
		return Main.forWindow(self.window) != None

class SublimeDebugOpenCommand(RunMainCommand):
	def run_main (self) -> None:
		main = Main.forWindow(self.window, True)
		assert main
		main.show()

class SublimeDebugToggleBreakpointCommand(RunMainCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window, True)
		assert main
		view = self.window.active_view()
		x, y = view.rowcol(view.sel()[0].begin())
		line = x + 1
		file = view.file_name()
		breakpoint = main.breakpoints.get_breakpoint(file, line)
		if breakpoint is not None:
			main.breakpoints.remove_breakpoint(breakpoint)
		else:
			main.breakpoints.add_breakpoint(file, line)

class SublimeDebugQuitCommand(RunMainCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main:
			main.dispose()

class SublimeDebugStartCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnPlay()
		
	def is_enabled(self) -> bool:
		main = Main.forWindow(self.window)
		if main and main.debugAdapterClient == None:
			return True
		return False
		
class SublimeDebugStopCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStop()
	def is_enabled(self) -> bool:
		main = Main.forWindow(self.window)
		if main and main.debugAdapterClient:
			return True
		return False

class SublimeDebugPauseCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnPause()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.running)

class SublimeDebugStepOverCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStepOver()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugStepInCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStepIn()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugStepOutCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnStepOut()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugResumeCommand(DebugWindowCommand):
	def run_main(self) -> None:
		main = Main.forWindow(self.window)
		if main: main.OnResume()
	def is_enabled(self) -> bool:
		return DebuggerInState(self.window, DebuggerState.stopped)

class SublimeDebugInstallAdapter(RunMainCommand):
	def run_main(self) -> None:
		self.adapters = list(get_setting(self.window.active_view(), "adapters").keys())
		self.adapters.insert(0, "Install All")
		self.window.show_quick_panel(self.adapters, self.install)

	def download(self, install_cfg: dict):
		import os
		import shutil
		import zipfile
		import gzip
		import urllib.request

		os.chdir(os.path.join(sublime.packages_path() ,"sublime_db/debug_adapters"))
		adapter_name = install_cfg.get("name", None)
		download_link = install_cfg.get("link", None)
		archive_format = install_cfg.get("format", None)
		if not adapter_name:
			print("No name for the adapter folder")
			return
		if not download_link:
			print("No download link found")
			return
		if not archive_format or archive_format not in ["zip", "zip.gz"]:
			print("The archive extension is not specified or incorrect")
		if os.path.isdir(adapter_name):
			print("Adapter %s already exists, deleting folder" % (adapter_name,))
			shutil.rmtree(adapter_name, ignore_errors=True)

		request = urllib.request.Request(download_link)
		response = urllib.request.urlopen(request)
		print(download_link)
		if response.getcode() != 200:
			print("Bad response from server, got code %d" % (response.getcode(),))
		os.mkdir(adapter_name)
		os.chdir(adapter_name)

		if archive_format == "zip.gz":
			# If it's a zip.gz we first apply zip.gz and then unzip it
			archive_format = "zip"
			response = gzip.GzipFile(fileobj=response)

		archive_name = "%s.%s" % (adapter_name, archive_format)
		with open(archive_name, "wb") as out_file:
			shutil.copyfileobj(response, out_file)

		if archive_format == "zip":
			with zipfile.ZipFile(archive_name) as zf:
				zf.extractall()

		os.remove(archive_name)
		os.chdir(sublime.packages_path())

	def install(self, adapter_id: int) -> None:
		install_list = []
		if adapter_id < 0:
			return
		if adapter_id == 0:
			# Installation of all adapters
			cfg = get_setting(self.window.active_view(), "adapters")
			for adapter in cfg.keys():
				install_cfg = cfg[adapter].get("installation", None)
				if install_cfg:
					install_list.append(install_cfg)
		if adapter_id > 0:
			cfg = get_setting(self.window.active_view(), "adapters")[self.adapters[adapter_id]]
			install_cfg = cfg.get("installation", None)
			if not install_cfg:
				print("No installation instruction found for adapter %s" % (self.adapters[adapter_id],))
				return
			install_list.append(install_cfg)
		for cfg in install_list:
			self.download(cfg)
