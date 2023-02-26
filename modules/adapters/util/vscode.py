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



class AdapterInstaller(dap.AdapterInstaller):
	type: str

	_package_info: AdapterInfo|None = None

	# def ensure_install_(self, url: str, name: str):

	async def install_from_asset(self, url: str, log: core.Logger, post_download_action: Callable[[], Awaitable[Any]]|None = None):
		try:
			del _info_for_type[self.type]
		except KeyError:
			...
		
		path = self.temporary_install_path()
		await request.download_and_extract_zip(url, path, log)

		if post_download_action:
			await post_download_action()

	
	def configuration_snippets(self, schema_type: str|None = None):
		if i := self.package_info():
			if contributes := i.schema_and_snippets.get(schema_type or self.type):
				return contributes['snippets']
			return None
		return None

	def configuration_schema(self, schema_type: str|None = None):
		if i := self.package_info():
			if contributes := i.schema_and_snippets.get(schema_type or self.type):
				return contributes['schema']
		return None

	def installed_version(self) -> str|None:
		if i := self.package_info():
			return i.version
		return None

	def package_info(self) -> AdapterInfo|None:
		if self._package_info:
			return self._package_info
		

		# check multiple places for the package.json
		extension = f'{self.install_path()}'

		if os.path.exists(f'{self.install_path()}/extension/package.json'):
			extension = f'{self.install_path()}/extension'
		else:
			extension = f'{self.install_path()}'

		if not os.path.exists(extension):
			return 

		version = '??'
		contributes: dict[str, Any] = {}
		strings: dict[str, str] = {}

		try:
			with open(f'{extension}/package.nls.json', encoding='utf8') as file:
				# add % so that we can just match string values directly in the package.json since we are only matching entire strings
				# strings_json = core.json_decode_readable(file)
				strings_json = json.load(file)
				strings = { F'%{key}%' : value for key, value in strings_json.items() }
		except:
			...

		try:
			with open(f'{extension}/package.json', encoding='utf8') as file:
				package_json = replace_localized_placeholders(json.load(file), strings)
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


@dataclass
class AdapterInfo:
	version: str
	schema_and_snippets: dict[str, Any]

def replace_localized_placeholders(json: Any, strings: dict[str, str]) -> Any:
	# print(type(json))
	if type(json) is str:
		return strings.get(json, json)

	if type(json) is list:
		return [replace_localized_placeholders(value, strings) for value in json]

	if type(json) is dict:
		return { key: replace_localized_placeholders(value, strings) for key, value in json.items() }

	return json


def attach_copy_logger(stream: IO[bytes], log_info, total, length=128*1024):
	copied = 0

	read = stream.read
	

	# def read_replacement(length: int = -1):
	# 	nonlocal copied
	# 	data = read(length)
	# 	copied += len(data)

	# 	if length > length:
	# 		copied = 0

	# 		# handle the case where the total size isn't known
	# 		if total:
	# 			log_info('{:.2f} mb {}%'.format(copied/1024/1024, int(copied/total*100)))
	# 		else:
	# 			log_info('{:.2f} mb'.format(copied/1024/1024))

	# 	return data
	
	# stream.read = read_replacement



