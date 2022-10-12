from __future__ import annotations
from typing import Any, ClassVar

from .import core
from .import dap

import sublime
import json


class AdaptersRegistry:
	all: ClassVar[list[dap.AdapterConfiguration]] = []
	types: ClassVar[dict[str, dap.AdapterConfiguration]] = {}

	@staticmethod
	def initialize():
		def subclasses(cls=dap.AdapterConfiguration):
			all_subclasses = []
			for subclass in cls.__subclasses__():
				subclasses_of_subclass = subclasses(subclass)
				if subclasses_of_subclass:
					all_subclasses.extend(subclasses_of_subclass)
				else:
					all_subclasses.append(subclass)

			return all_subclasses

		# create and register all the adapters
		for klass in subclasses():
			AdaptersRegistry.register(klass())

	@staticmethod
	def register(adapter: dap.AdapterConfiguration):
		AdaptersRegistry.all.append(adapter)
		
		AdaptersRegistry.types[adapter.type] = adapter
		for type in adapter.types:
			AdaptersRegistry.types[type] = adapter

	@staticmethod
	def get(type: str) -> dap.AdapterConfiguration:
		if adapter := AdaptersRegistry.types.get(type):
			return adapter

		raise core.Error(f'Unable to find debug adapter with the type name "{type}"')


	@staticmethod
	def format_snippet(snippet: dict[str, Any]):
		body = snippet.get('body', {})
		for (key, value) in snippet.items():
			if isinstance(value, str) and value.startswith('^"') and value.endswith('"'):
				body[key] = value[2:-1]

		content = json.dumps(body, indent="\t")
		content = content.replace('\\\\', '\\') # remove json encoded \ ...
		content = content.replace('${workspaceFolder}', '${folder}')
		content = content.replace('${workspaceRoot}', '${folder}')
		return content

	@staticmethod
	async def _insert_snippet(window: sublime.Window, snippet: dict[str, Any]):
		for (key, value) in snippet.items():
			if isinstance(value, str) and value.startswith('^"') and value.endswith('"'):
				snippet[key] = value[2:-1]

		content = json.dumps(snippet, indent="\t")
		content = content.replace('\\\\', '\\') # remove json encoded \ ...
		content = content.replace('${workspaceFolder}', '${folder}')
		content = content.replace('${workspaceRoot}', '${folder}')

		try:

			project = window.project_file_name()
			if not project:
				raise core.Error('Expected project file in window')

			view = await core.sublime_open_file_async(window, project)
			region = view.find(r'''"\s*debugger_configurations\s*"\s*:\s*\[''', 0)
			if not region:
				raise core.Error('Unable to find debugger_configurations')

			view.sel().clear()
			view.sel().add(sublime.Region(region.b, region.b))
			view.run_command('insert', {
				'characters': '\n'
			})
			view.run_command('insert_snippet', {
				'contents': content + ','
			})

		except core.Error:
			core.exception()
			sublime.set_clipboard(content)
			core.display('Unable to insert configuration into sublime-project file: Copied to clipboard instead')


	@staticmethod
	def recalculate_schema():
		from .schema import save_schema
		save_schema(AdaptersRegistry.all)
