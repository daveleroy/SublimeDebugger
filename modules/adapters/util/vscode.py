from __future__ import annotations
from typing import BinaryIO
from ...typecheck import *
from ...import core

import os
import shutil
import zipfile
import gzip
import urllib.request
import json
import pathlib
import certifi


from dataclasses import dataclass

_info_for_type: dict[str, AdapterInfo] = {}


def install_path(type: str) -> str:
	return f'{core.current_package()}/data/adapters/{type}'

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

def info(type: str) -> Optional[AdapterInfo]:
	info = _info_for_type.get(type)
	if info:
		return info

	path = f'{core.current_package()}/data/adapters/{type}'

	if not os.path.exists(path):
		return None

	version = '??'
	contributes: dict[str, Any] = {}
	
	strings: dict[str, str] = {}

	try:
		with open(f'{path}/extension/package.nls.json', encoding='utf8') as file:
			# add % so that we can just match string values directly in the package.json since we are only matching entire strings
			# strings_json = core.json_decode_readable(file)
			strings_json = json.load(file)
			strings = { F'%{key}%' : value for key, value in strings_json.items() }
	except:
		...

	with open(f'{path}/extension/package.json', encoding='utf8') as file:
		package_json = replace_localized_placeholders(json.load(file), strings)
		version = package_json.get('version')
		for debugger in package_json.get('contributes', {}).get('debuggers', []):
			debugger_type = debugger.get('type') or type
			contributes[debugger_type] = {
				'snippets': debugger.get('configurationSnippets', []),
				'schema': debugger.get('configurationAttributes', {}),
			}

	info = AdapterInfo(
		version=version,
		schema_and_snippets=contributes,
	)
	_info_for_type[type] = info
	return info

def installed_version(type: str) -> str|None:
	if i := info(type):
		return i.version
	return None

def configuration_schema(type: str, vscode_type: str|None = None) -> dict[str, Any] | None:
	if i := info(type):
		if contributes := i.schema_and_snippets.get(vscode_type or type):
			return contributes['schema']

	return None

def configuration_snippets(type: str, vscode_type: str|None = None) -> list[Any] | None:
	if i := info(type):
		if contributes := i.schema_and_snippets.get(vscode_type or type):
			return contributes['snippets']

	return None



@dataclass
class Config:
	headers: dict[str, str]|None = None
	body: bytes|None = None
	method: str|None = None


@dataclass
class Response:
	headers: dict[str, str]
	data: BinaryIO

async def request(url: str, config: Config = Config()):
	headers = {
		'Accept-Encoding': 'gzip, deflate'
	}
	if config.headers:
		for h, v in config.headers.items():
			headers[h] = v

	request = urllib.request.Request(url, headers=headers, data=config.body)
	response = urllib.request.urlopen(request, cafile=certifi.where())

	content_encoding = response.headers.get('Content-Encoding')
	if content_encoding == 'gzip':
		data_file = gzip.GzipFile(fileobj=response) #type: ignore
	elif content_encoding == 'deflate':
		data_file = response
	elif content_encoding:
		raise core.Error(f'Unknown Content-Encoding {content_encoding}')
	else:
		data_file = response

	return Response(headers=response.headers, data=data_file) #type: ignore

# async def request_json(url: str, config: Config):
# 	file = request(url, config)
# 	return json file.read()

async def install(type: str, url: str, log: core.Logger, post_download_action: Optional[Callable[[], Awaitable[Any]]] = None):
	try:
		del _info_for_type[type]
	except KeyError:
		...
	
	def log_info(value: str):
		core.call_soon_threadsafe(log.info, value)

	path = install_path(type)
	temporary_path = path + '_temp'

	# ensure adapters folder exists
	adapters_path = pathlib.Path(path).parent

	if not adapters_path.is_dir():
		adapters_path.mkdir()

	if os.path.isdir(path):
		log_info('removing previous installation...')
		shutil.rmtree(_abspath_fix(path))
		log_info('...removed')

	if os.path.isdir(temporary_path):
		log_info('removing previous temporary installation...')
		shutil.rmtree(_abspath_fix(path))
		log_info('...removed')


	log_info('downloading...')
	response = await request(url)

	def blocking():
		
		os.mkdir(temporary_path)	

		archive_name = '{}.zip'.format(path)
		with open(archive_name, 'wb') as out_file:
			copyfileobj(response.data, out_file, log_info, int(response.headers.get('Content-Length', '0')))

		log_info('...downloaded')

		log_info('extracting...')
		with ZipfileLongPaths(archive_name) as zf:
			zf.extractall(temporary_path)
		log_info('...extracted')
		os.remove(archive_name)
		os.rename(temporary_path, path)


	log.info(f'Installing adapter: {type}')
	log.info('from: {}'.format(url))

	await core.run_in_executor(blocking)
	if post_download_action:
		await post_download_action()


	# successfully installed so add a marker file
	path_installed = f'{path}/.sublime_debugger'
	with open(path_installed, 'w') as file_installed:
		...


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