from ...typecheck import *
from ..import adapter
from ..util import get_debugger_setting

class Python(adapter.Adapter):

	@property
	def type(self): return 'python'

	async def start(self, log):
		use_debugpy = get_debugger_setting('python.experimental_debugpy_adapter', False)
		install_path = adapter.vscode.install_path(self.type)

		if use_debugpy:
			command = [
				'python3', # probably doesn't work cross platform?
				f'{install_path}/extension/pythonFiles/lib/python/debugpy/wheels/debugpy/adapter',
			]
			log.info("Using experimental debugpy adapter")
		else:
			node = adapter.get_and_warn_require_node_less_than_or_equal(self.type, log, 'v12.5.0')
			command = [
				node,
				f'{install_path}/extension/out/client/debugger/debugAdapter/main.js'
			]

		return adapter.StdioTransport(log, command)

	async def install(self, log):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/ms-python/vsextensions/python/latest/vspackage'
		await adapter.vscode.install(self.type, url, log)
		
	@property
	def installed_version(self) -> Optional[str]: 
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self) -> list: 
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self) -> dict: 
		return adapter.vscode.configuration_schema(self.type)

	# TODO: patch in env since python seems to not inherit it from the adapter proccess.
	def configuration_resolve(self, configuration):
		if configuration.request == "launch":
			if not configuration.get("program"):
				sublime.error_message("Warning: Check your debugger configuration.\n\nField `program` in configuration is empty. If it contained a $variable that variable may not have existed.""")
		
		return configuration
