from ..typecheck import *

import os
import shutil
import zipfile
import gzip
import urllib.request
import sublime
import json

from .. import core


def _adapters_path() -> str:
	return os.path.join(core.current_package(), "data", "debug_adapters")


class AdapterConfiguration:
	class Installation:
		def __init__(self, name: str, url: str, format: str) -> None:
			self.name = name
			self.url = url
			self.format = format

		@staticmethod
		def from_json(json: dict) -> 'AdapterConfiguration.Installation':
			return AdapterConfiguration.Installation(json['name'], json['url'], json['format'])

	def __init__(self, type: str, json: dict) -> None:

		self.command = json['command']

		vscode_package_file = json.get('vscode-package-file')


		install_json = json.get('installation')
		installation = None
		if install_json:
			installation = AdapterConfiguration.Installation.from_json(install_json)

		self.type = type
		self.hover_word_seperators = json.get('hover_word_seperators')
		self.hover_word_regex_match = json.get('hover_word_regex_match')
		self.tcp_port = json.get('tcp_port')
		self.tcp_address = json.get('tcp_address')
		self.vscode_package_file = vscode_package_file
		self.snippets = [] #type: List[dict]
		self.installation = installation
		self.installed = True
		self.installing = False
		self.load_installation_if_needed()

	def load_installation_if_needed(self) -> None:
		if not self.installation:
			return

		self.installed = os.path.isdir(os.path.join(_adapters_path(), self.installation.name))
		snippets_file = os.path.join(os.path.join(_adapters_path(), self.installation.name, 'snippets.json'))
		try:
			with open(snippets_file) as file:
				self.snippets = json.load(file)
		except Exception as e:
			core.log_info('No snippets loaded. {}'.format(e))

	@staticmethod
	def from_json(type: str, json: dict) -> 'AdapterConfiguration':
		return AdapterConfiguration(
			type,
			json,
		)


class Configuration:
	def __init__(self, name: str, type: str, request: str, all: dict, expand_platforms: bool = True) -> None:
		self.name = name
		self.type = type
		self.index = -1
		self.request = request

		self.all = all

		if expand_platforms:
			if core.platform.osx:
				platform = self.all.get('osx', {})
			elif core.platform.linux:
				platform = self.all.get('linux', {})
			elif core.platform.windows:
				platform = self.all.get('windows', {})
			else:
				platform = {}

			for item in platform.items():
				self.all[item[0]] = item[1]

	@staticmethod
	def from_json(json: dict) -> 'Configuration':
		name = json.get('name')
		assert name, 'expecting name for debug.configuration'
		type = json.get('type')
		assert type, 'expecting type for debug.configuration'
		request = json.get('request')
		assert request, 'expecting request for debug.configuration'
		return Configuration(name, type, request, json)


class ConfigurationExpanded(Configuration):
	def __init__(self, configuration: Configuration, variables: Any) -> None:
		all = sublime.expand_variables(configuration.all, variables)
		super().__init__(configuration.name, configuration.type, configuration.request, all, expand_platforms=False)
		self.verify()

	def verify(self):
		def warn(text: str):
			sublime.error_message(text)

		def error(text: str):
			raise core.Error(text)

		if self.type == "python":
			if self.request == "launch":
				if not self.all.get("program"):
					warn("Warning: Check your debugger configuration.\n\nField `program` in configuration is empty. If it contained a $variable that variable may not have existed.""")
			return

@core.async
def install_adapter(adapter: AdapterConfiguration) -> core.awaitable[None]:
	try:
		assert adapter.installation
		yield from core.run_in_executor(_install_adapter_blocking, adapter)

		vscode_package_file = os.path.join(_adapters_path(), adapter.installation.name, 'extension', 'package.json')
		snippets_output_file = os.path.join(_adapters_path(), adapter.installation.name, 'snippets.json')

	
		snippets = [] #type: List[dict]
		with open(vscode_package_file) as file:
			j = json.load(file)
			for debugger in j['contributes']['debuggers']:
				snippets.extend(debugger.get('configurationSnippets', []))

		with open(snippets_output_file, 'w') as file:
			content = json.dumps(snippets)

			# strip out unescaped stuff
			# FIXME this isn't correct... but good enough for now...
			content = content.replace('^\\\"', '')
			content = content.replace('\\\"', '')
			file.write(content)

		print('snippets found: ', snippets)
	except Exception as e:
		print('Failed to find debug configuration snippets in vscode package.json file, ', str(e))

	adapter.load_installation_if_needed()

def _install_adapter_blocking(adapter: AdapterConfiguration):
	install_cfg = adapter.installation
	assert install_cfg, 'No install information for this adapter configuration'

	adapters_path = _adapters_path()
	adapter_name = install_cfg.name

	if not os.path.isdir(adapters_path):
		os.mkdir(adapters_path)

	url = install_cfg.url
	archive_format = install_cfg.format

	if archive_format not in ["zip"]:
		raise Exception("The archive extension is incorrect")

	adapter_path = os.path.join(adapters_path, adapter_name)

	if os.path.isdir(adapter_path):
		print("Adapter %s already exists, deleting folder" % (adapter_path,))
		shutil.rmtree(adapter_path, ignore_errors=True)

	request = urllib.request.Request(url, headers={
		"Accept-Encoding": "gzip"
	})

	response = urllib.request.urlopen(request)
	if response.getcode() != 200:
		raise Exception("Bad response from server, got code %d" % (response.getcode(),))
	os.mkdir(adapter_path)

	content_encoding = response.headers.get('Content-Encoding')
	if content_encoding == 'gzip':
		response = gzip.GzipFile(fileobj=response) #type: ignore

	archive_name = "%s.%s" % (adapter_path, archive_format)
	with open(archive_name, "wb") as out_file:
		shutil.copyfileobj(response, out_file)

	if archive_format == "zip":
		with ZipfileLongPaths(archive_name) as zf:
			zf.extractall(adapter_path)

	os.remove(archive_name)

# Fix for long file paths on windows not being able to be extracted from a zip file
# https://stackoverflow.com/questions/40419395/python-zipfile-extractall-ioerror-on-windows-when-extracting-files-from-long-pat
class ZipfileLongPaths(zipfile.ZipFile):
	def _path(self, path, encoding=None):
		path = os.path.abspath(path)
		if core.platform.windows:
			if path.startswith("\\\\"):
				path = "\\\\?\\UNC\\" + path[2:]
			else:
				path = "\\\\?\\" + path
		return path

	def _extract_member(self, member, targetpath, pwd):
		targetpath = self._path(targetpath)
		return zipfile.ZipFile._extract_member(self, member, targetpath, pwd)
