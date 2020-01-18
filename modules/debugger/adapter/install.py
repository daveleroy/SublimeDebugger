from ...typecheck import *
from ...import core
from ...libs import certifi

import os
import shutil
import zipfile
import gzip
import urllib.request
import json
import sublime


def _adapters_path() -> str:
	return os.path.join(core.current_package(), 'data', 'debug_adapters')


class AdapterInstall:
	async def install(self, log: core.Logger) -> None: ...

	@property
	def installed(self) -> bool: ...
	def installed_info(self) -> 'AdapterInstalledInformation': ...


class AdapterInstalledInformation:
	def __init__(self, version: int, snippets: list):
		self.version = version
		self.snippets = snippets


class VSCodeAdapterInstall:
	def __init__(self, name: str, url: str) -> None:
		self.name = name
		self.url = url
		self.path = os.path.join(_adapters_path(), self.name)

	@staticmethod
	def from_json(json: dict) -> 'VSCodeAdapterInstall':
		return VSCodeAdapterInstall(json['name'], json['url'])

	@property
	def installed(self) -> bool:
		return os.path.isfile(os.path.join(self.path, 'sublime_debugger.json'))

	def installed_info(self) -> AdapterInstalledInformation:
		snippets_output_file = os.path.join(self.path, 'sublime_debugger.json')
		snippets_file_exists = os.path.isfile(snippets_output_file)
		if snippets_file_exists:
			with open(snippets_output_file) as file:
				j = json.load(file)
				return AdapterInstalledInformation(j.get('version', 0), j['configurationSnippets'])

		return AdapterInstalledInformation(0, [])

	async def install(self, log: core.Logger) -> None:
		try:
			log.info('Installing adapter: {}'.format(self.name))
			await core.run_in_executor(self.downalod_and_extract_blocking, log)

			vscode_package_file = os.path.join(self.path, 'extension', 'package.json')
			snippets_output_file = os.path.join(self.path, 'sublime_debugger.json')
			snippets = [] #type: List[dict]

			with open(vscode_package_file, "rb") as file:
				j = sublime.decode_value(file.read().decode('utf-8'))
				version = j.get('version')
				for debugger in j.get('contributes', {}).get('debuggers', []):
					snippets.extend(debugger.get('configurationSnippets', []))

			with open(snippets_output_file, 'w') as snippets_file:
				sublime_adapter_info = {
					'configurationSnippets': snippets,
					'version': version
				}
				content = json.dumps(sublime_adapter_info)

				# strip out unescaped stuff
				# FIXME this isn't correct... but good enough for now...
				content = content.replace('^\\\"', '')
				content = content.replace('\\\"', '')
				snippets_file.write(content)

			log.info('Finished Installing adapter: {}'.format(self.name))
		except Exception as e:
			log.info('Failled Finished Installing adapter: {}'.format(e))

	def downalod_and_extract_blocking(self, log: core.Logger):
		def log_info(value: str):
			core.call_soon_threadsafe(log.info, value)

		# ensure adapters folder exists
		adapters_path = _adapters_path()
		if not os.path.isdir(adapters_path):
			os.mkdir(adapters_path)

		if os.path.isdir(self.path):
			log_info('Removing existing adapter...')
			shutil.rmtree(_abspath_fix(self.path))
			log_info('done')

		log_info('downloading: {}'.format(self.url))
		request = urllib.request.Request(self.url, headers={
			'Accept-Encoding': 'gzip'
		})

		response = urllib.request.urlopen(request, cafile=certifi.where())
		if response.getcode() != 200:
			raise core.Error('Bad response from server, got code {}'.format(response.getcode()))
		os.mkdir(self.path)

		content_encoding = response.headers.get('Content-Encoding')
		if content_encoding == 'gzip':
			data_file = gzip.GzipFile(fileobj=response) #type: ignore
		else:
			data_file = response

		archive_name = '{}.zip'.format(self.path)
		with open(archive_name, 'wb') as out_file:
			copyfileobj(data_file, out_file, log_info, int(response.headers.get('Content-Length', '0')))

		log_info('extracting zip... ')
		with ZipfileLongPaths(archive_name) as zf:
			zf.extractall(self.path)
		log_info('done')
		os.remove(archive_name)

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

	def extract(self, member, path=None, pwd=None):
		if not isinstance(member, zipfile.ZipInfo):
			member = self.getinfo(member)

		if path is None:
			path = os.getcwd()

		ret_val = self._extract_member(member, path, pwd)
		attr = member.external_attr >> 16
		os.chmod(ret_val, attr)
		return ret_val

	def _extract_member(self, member, targetpath, pwd):
		targetpath = self._path(targetpath)
		return zipfile.ZipFile._extract_member(self, member, targetpath, pwd) #type: ignore


def _abspath_fix(path):
	if core.platform.windows:
		path = os.path.abspath(path)
		if path.startswith("\\\\"):
			path = "\\\\?\\UNC\\" + path[2:]
		else:
			path = "\\\\?\\" + path
	return path
