from ...typecheck import *
from ...import core

import os
import shutil
import zipfile
import gzip
import urllib.request
import json
import sublime
from dataclasses import dataclass
import ssl
import pathlib
import certifi
import uuid

_info_for_type = {} #type: Dict[str, Optional[AdapterInfo]]


def install_path(type: str) -> str:
	return f'{core.current_package()}/data/adapters/{type}'

@dataclass
class AdapterInfo:
	version: str
	schema_and_snippets: dict

def info(type: str) -> Optional[AdapterInfo]:
	info = _info_for_type.get(type)
	if info:
		return info

	path = f'{core.current_package()}/data/adapters/{type}'
	path_installed = f'{path}/.sublime_debugger'

	if not os.path.exists(path_installed):
		return None

	version = "??"
	snippets = []
	schema = {}
	contributes = {}

	with open(f'{path}/extension/package.json') as file:
		package_json = json.load(file)
		version = package_json.get('version')
		for debugger in package_json.get('contributes', {}).get('debuggers', []):
			debugger_type = debugger.get('type') or type

			contributes[debugger_type] = {
				'snippets': debugger.get('configurationSnippets', []),
				'schema': debugger.get('configurationAttributes', {})
			}

	info = AdapterInfo(
		version=version,
		schema_and_snippets=contributes,
	)
	_info_for_type[type] = info
	return info

def installed_version(type: str) -> Optional[str]:
	if i := info(type):
		return i.version
	return None

def configuration_schema(type: str, vscode_type: Optional[str] = None) -> Optional[dict]:
	if i := info(type):
		contributes = i.schema_and_snippets.get(vscode_type or type)
		if contributes:
			return contributes['schema']

	return None

def configuration_snippets(type: str, vscode_type: Optional[str] = None) -> Optional[list]:
	if i := info(type):
		contributes = i.schema_and_snippets.get(vscode_type or type)
		if contributes:
			return contributes['snippets']

	return None

async def install(type: str, url: str, log: core.Logger):
	try:
		del _info_for_type[type]
	except KeyError:
		...
	path = install_path(type)

	def blocking():
		def log_info(value: str):
			core.call_soon_threadsafe(log.info, value)

		# ensure adapters folder exists
		adapters_path = pathlib.Path(path).parent

		if not adapters_path.is_dir():
			adapters_path.mkdir()

		if os.path.isdir(path):
			log_info('removing previous installation...')
			shutil.rmtree(_abspath_fix(path))
			log_info('...removed')

		log_info('downloading...')
		request = urllib.request.Request(url, headers={
			'Accept-Encoding': 'gzip',
			'X-Market-User-Id': str(uuid.uuid4()),
		})
		response = urllib.request.urlopen(request, cafile=certifi.where())
		os.mkdir(path)

		content_encoding = response.headers.get('Content-Encoding')
		if content_encoding == 'gzip':
			data_file = gzip.GzipFile(fileobj=response) #type: ignore
		else:
			data_file = response

		archive_name = '{}.zip'.format(path)
		with open(archive_name, 'wb') as out_file:
			copyfileobj(data_file, out_file, log_info, int(response.headers.get('Content-Length', '0')))

		log_info('...downloaded')

		log_info('extracting...')
		with ZipfileLongPaths(archive_name) as zf:
			zf.extractall(path)
		log_info('...extracted')
		os.remove(archive_name)

	log.info(f'Installing adapter: {type}')
	log.info('from: {}'.format(url))

	try:
		await core.run_in_executor(blocking)
	except Exception as error:
		log.error(f'Failed to install adapter: {str(error)}')
		return

	# successfully installed so add a marker file
	path_installed = f'{path}/.sublime_debugger'
	with open(path_installed, 'w') as file_installed:
		...

	log.info('Successfully Installed Adapter!')

	from .adapters import Adapters
	Adapters.recalculate_schema()

# https://stackoverflow.com/questions/29967487/get-progress-back-from-shutil-file-copy-thread
def copyfileobj(fsrc, fdst, log_info, total, length=128*1024):
	copied = 0
	while True:
		buf = fsrc.read(length)
		if not buf:
			break
		fdst.write(buf)
		copied += len(buf)
		log_info("{:.2f} mb {}%".format(copied/1024/1024, int(copied/total*100)))

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
		if path.startswith("\\\\"):
			path = "\\\\?\\UNC\\" + path[2:]
		else:
			path = "\\\\?\\" + path
	return path