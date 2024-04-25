from __future__ import annotations
from dataclasses import dataclass
import json
from typing import IO, Any, Awaitable, Callable

from ...import core
from ...import dap

from . import request

import os
import sublime


_info_for_type: dict[str, AdapterInfo] = {}

@dataclass
class AdapterInfo:
	version: str
	schema_and_snippets: dict[str, Any]

class AdapterInstaller(dap.AdapterInstaller):
	type: str

	_package_info: AdapterInfo|None = None

	def remove(self):
		super().remove()
		self._package_info = None

	async def install_vsix(self, url: str, *, log: core.Logger):
		try:
			del _info_for_type[self.type]
		except KeyError:
			...

		path = self.temporary_install_path()
		await request.download_and_extract_zip(url, path, 'extension', log=log)


	async def install_source(self, url: str, *, log: core.Logger):
		try:
			del _info_for_type[self.type]
		except KeyError:
			...

		path = self.temporary_install_path()
		await request.download_and_extract_zip(url, path, log=log)

	def configuration_snippets(self, schema_type: str|None = None):
		if i := self.package_info():
			if contributes := i.schema_and_snippets.get(schema_type or self.type):
				return contributes['snippets']
		return []

	def configuration_schema(self, schema_type: str|None = None):
		if i := self.package_info():
			if contributes := i.schema_and_snippets.get(schema_type or self.type):
				return contributes['schema']
		return {}

	def installed_version(self) -> str|None:
		if i := self.package_info():
			return i.version
		return None

	def package_info(self) -> AdapterInfo|None:
		if self._package_info:
			return self._package_info

		if not os.path.exists(f'{self.install_path()}/package.json'):
			return

		version = '??'
		contributes: dict[str, Any] = {}
		strings: dict[str, str] = {}

		try:
			with open(f'{self.install_path()}/package.nls.json', encoding='utf8') as file:
				# add % so that we can just match string values directly in the package.json since we are only matching entire strings
				# strings_json = core.json_decode_readable(file)
				strings_json = json.load(file)
				strings = { F'%{key}%' : value for key, value in strings_json.items() }
		except:
			...

		try:
			with open(f'{self.install_path()}/package.json', encoding='utf8') as file:
				package_json = self._replace_localized_placeholders(json.load(file), strings)
				version = package_json.get('version')
				for debugger in package_json.get('contributes', {}).get('debuggers', []):
					debugger_type = debugger.get('type') or self.type
					contributes[debugger_type] = {
						'snippets': debugger.get('configurationSnippets', []),
						'schema': debugger.get('configurationAttributes', {}),
					}

		except:
			core.exception()
			return None

		info = AdapterInfo(
			version=version,
			schema_and_snippets=contributes,
		)
		self._package_info = info
		return self._package_info


	def _replace_localized_placeholders(self, json: Any, strings: dict[str, str]) -> Any:
		# print(type(json))
		if type(json) is str:
			return strings.get(json, json)

		if type(json) is list:
			return [self._replace_localized_placeholders(value, strings) for value in json]

		if type(json) is dict:
			return { key: self._replace_localized_placeholders(value, strings) for key, value in json.items() }

		return json
