from ...typecheck import *
from ..import adapter
from ...import core
from ..adapter.transports import SocketTransport, Process
from ..util import get_debugger_setting

import subprocess
import re
import threading

class LLDBTransport(SocketTransport):
	def __init__(self, log: core.Logger, command: List[str], cwd: Optional[str] = None):
		self.process = Process(command, cwd)

		line = self.process.stdout.readline().decode('utf-8')
		result = re.match(r'Listening on port (.*)', line)
		port = int(result.group(1))

		super().__init__(log, 'localhost', port, cwd)

		thread = threading.Thread(target=self._read, args=(self.process.stderr, lambda line: log.log('process', line)))
		thread.start()

	def _read(self, file: Any, callback: Callable[[str], None]) -> None:
		while True:
			try:
				line = file.read(2**15).decode('UTF-8')
				if not line:
					core.log_info("Nothing to read from process, closing")
					break
				core.log_info(line)
				core.call_soon_threadsafe(callback, line)
			except Exception as e:
				core.log_exception()
				break

	def dispose(self) -> None:
		self.process.dispose()


class LLDB(adapter.Adapter):
	@property
	def type(self):
		return "lldb"

	async def start(self, log: core.Logger, configuration):
		install_path = adapter.vscode.install_path(self.type)

		codelldb = f'{install_path}/extension/adapter/codelldb'
		libpython = get_debugger_setting('lldb.Python')
		if not libpython:
			libpython = subprocess.check_output([codelldb, "find-python"]).strip()

		libLLDB = get_debugger_setting('lldb.Library')
		command = [
			codelldb,
			"--libpython", libpython
		]

		if libLLDB:
			command.extend(["--liblldb", libLLDB])

		return LLDBTransport(log, command)

	async def install(self, log: core.Logger):
		if core.platform.windows:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-windows.vsix'
		if core.platform.osx:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-darwin.vsix'
		if core.platform.linux:
			url = 'https://github.com/vadimcn/vscode-lldb/releases/latest/download/codelldb-x86_64-linux.vsix'

		await adapter.vscode.install(self.type, url, log)

	@property
	def installed_version(self) -> Optional[str]:
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> Optional[list]:
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> Optional[dict]:
		return adapter.vscode.configuration_schema(self.type)
