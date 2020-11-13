from ..typecheck import *
from ..import core
from ..import dap
from .import adapter

import shutil
import re
import subprocess

# this is what the example configuration in examples/dart/dart.sublime-project sent to the dart adapter when using vscode

# {
#     "name": "Dart",
#     "type": "dart",
#     "request": "launch",
#     "program": ".../Packages/Debugger/examples/dart/main.dart",
#     "__configurationTarget": 5,
#     "cwd": ".../Packages/Debugger/examples",
#     "dartVersion": "2.10.3",
#     "toolEnv": {
#         "FLUTTER_HOST": "VSCode",
#         "PUB_ENVIRONMENT": "vscode.dart-code"
#     },
#     "sendLogsToClient": true,
#     "args": [],
#     "vmAdditionalArgs": [],
#     "vmServicePort": 0,
#     "dartPath": "../dart",
#     "maxLogLineLength": 2000,
#     "pubPath": "../pub",
#     "pubSnapshotPath": "../snapshots/pub.dart.snapshot",
#     "debugSdkLibraries": false,
#     "debugExternalLibraries": false,
#     "showDartDeveloperLogs": true,
#     "evaluateGettersInDebugViews": true,
#     "evaluateToStringInDebugViews": true,
#     "debuggerType": 0
# }

class Dart(adapter.AdapterConfiguration):
	type = "dart"

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		node = await adapter.get_and_warn_require_node(self.type, log)
		install_path = adapter.vscode.install_path(self.type)
		command = [
			node,
			f'{install_path}/extension/out/dist/debug.js',
			'dart'
		]
		return adapter.StdioTransport(log, command)

	async def install(self, log: core.Logger):
		url = 'https://marketplace.visualstudio.com/_apis/public/gallery/publishers/Dart-Code/vsextensions/dart-code/latest/vspackage'
		await adapter.vscode.install(self.type, url, log)

	async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
		# patch in dartPath and dartVersion
		# that seems to be the minimum required options for the test example
		# other configurations are likely to require more

		dart = shutil.which('dart')
		if not dart:
			raise core.Error("Unable to find dart")

		version = (await adapter.Process.check_output([dart, '--version'], stderr=subprocess.STDOUT)).decode('utf-8')
		version_match = re.match(r'Dart SDK version: (\d+\.\d+\.\d+)', version)

		if (not version_match):
			raise core.Error("Unable to find dart version")

		configuration['dartPath'] = dart
		configuration['dartVersion'] = version_match[1]

		return configuration

	@property
	def installed_version(self):
		return adapter.vscode.installed_version(self.type)

	@property
	def configuration_snippets(self):
		return adapter.vscode.configuration_snippets(self.type)

	@property
	def configuration_schema(self):
		return adapter.vscode.configuration_schema(self.type)