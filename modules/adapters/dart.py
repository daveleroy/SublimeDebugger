from ..typecheck import *
from ..import core
from ..import dap
from .import adapter

import shutil

# See https://github.com/dart-lang/sdk/blob/main/pkg/dds/tool/dap/README.md

class Dart(adapter.AdapterConfiguration):
	type = 'dart'

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		if not shutil.which('dart'):
			raise core.Error('You must install `dart` see https://dart.dev/get-dart')

		command = [
			'dart',
			'debug_adapter',
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		...

	@property
	def installed_version(self):
		return '???'

	@property
	def configuration_snippets(self):
		return []

	@property
	def configuration_schema(self):
		return {}

