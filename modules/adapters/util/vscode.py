from __future__ import annotations
from typing import Any, Awaitable, Callable

from ...import core
from ...import dap

from . import request

import os
import shutil
import zipfile
import json
import pathlib
import sublime

from dataclasses import dataclass

_info_for_type: dict[str, AdapterInfo] = {}

class AdapterInstaller(dap.AdapterInstaller):
	type: str

	_package_info: AdapterInfo|None = None

	async def install_from_asset(self, url: str, log: core.Logger, post_download_action: Callable[[], Awaitable[Any]]|None = None):
		try:
			del _info_for_type[self.type]
		except KeyError:
			...
		
		def log_info(value: str):
			sublime.status_message(f'Debugger: {value}')
			# core.call_soon_threadsafe(log.info, value)

		path = self.install_path()
		temporary_path = path + '_temp'

		# ensure adapters folder exists
		adapters_path = pathlib.Path(path).parent
		
		archive_name = '{}.zip'.format(path)

		if not adapters_path.is_dir():
			adapters_path.mkdir()

		_remove_files_or_directories([path, temporary_path, archive_name])

		log_info('downloading...')
		response = await request.request(url)

		def blocking():
			
			os.mkdir(temporary_path)	

			archive_name = '{}.zip'.format(path)
			with open(archive_name, 'wb') as out_file:
				copyfileobj(response.data, out_file, log_info, int(response.headers.get('Content-Length', '0')))

			log_info('...downloaded')

			log_info('extracting...')
			with ZipfileLongPaths(archive_name) as zf:
				top = {item.split('/')[0] for item in zf.namelist()}
				zf.extractall(temporary_path)

				# if the zip is a single item rename it
				if len(top) == 1:
					os.rename(os.path.join(temporary_path, top.pop()), os.path.join(temporary_path, 'extension'))

			log_info('...extracted')
			os.remove(archive_name)
			os.rename(temporary_path, path)


		log.info('Downloading {}'.format(url))

		try:
			await core.run_in_executor(blocking)
			if post_download_action:
				await post_download_action()
		finally:
			_remove_files_or_directories([temporary_path, archive_name])

	async def uninstall(self):
		try:
			del _info_for_type[self.type]
		except KeyError:
			...

		_remove_files_or_directories([self.install_path()])

	
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

	def install_path(self) -> str: 
		return f'{core.package_path()}/data/adapters/{self.type}'


	def package_info(self) -> AdapterInfo|None:
		if self._package_info:
			return self._package_info

		extension = f'{self.install_path()}/extension'
		if not os.path.exists(extension):
			return None

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



def _remove_files_or_directories(paths: list[str]):
	for p in paths:
		if os.path.isdir(p):
			core.debug(f'removing previous directory: {p}')
			shutil.rmtree(_abspath_fix(p))

		elif os.path.isfile(p):
			core.debug(f'removing previous file: {p}')
			os.remove(p)



# https://stackoverflow.com/questions/29967487/get-progress-back-from-shutil-file-copy-thread
def copyfileobj(fsrc, fdst, log_info, total, length=128*1024):
	copied = 0

	while True:
		buf = fsrc.read(length)
		if not buf:
			break
		fdst.write(buf)
		copied += len(buf)
		
		# handle the case where the total size isn't known
		if total:
			log_info('{:.2f} mb {}%'.format(copied/1024/1024, int(copied/total*100)))
		else:
			log_info('{:.2f} mb'.format(copied/1024/1024))

# Fix for long file paths on windows not being able to be extracted from a zip file
# Fix for extracted files losing their permission flags
# https://stackoverflow.com/questions/40419395/python-zipfile-extractall-ioerror-on-windows-when-extracting-files-from-long-pat
# https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries
class ZipfileLongPaths(zipfile.ZipFile):
	def _path(self, path, encoding=None):
		return _abspath_fix(path)

	def _extract_member(self, member, targetpath, pwd):
		if not isinstance(member, zipfile.ZipInfo):
			member = self.getinfo(member)

		targetpath = self._path(targetpath)
		ret_val = zipfile.ZipFile._extract_member(self, member, targetpath, pwd) #type: ignore

		attr = member.external_attr >> 16
		if attr != 0:
			os.chmod(ret_val, attr)
		return ret_val

def _abspath_fix(path):
	if core.platform.windows:
		path = os.path.abspath(path)
		if path.startswith('\\\\'):
			path = '\\\\?\\UNC\\' + path[2:]
		else:
			path = '\\\\?\\' + path
	return path