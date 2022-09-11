from __future__ import annotations
from ...typecheck import *
from ...import core

import urllib.request
import urllib.error
import json
import certifi

from ...import dap
from .import vscode

from ...libs.semver import semver

cached_etag: dict[str, str] = {}
cached_response: dict[str, Any] = {}

# we have 60 requests per hour for an anonymous user to the github api
# conditional requests don't count against the 60 requests per hour limit so implement some very basic caching
# see https://docs.github.com/en/rest/overview/resources-in-the-rest-api
async def request_json(url: str, timeout: int|None = 30) -> Any:
	def blocking():
		headers = {
			'User-Agent': 'Sublime-Debugger',
		}
		if etag := cached_etag.get(url):
			headers['If-None-Match'] = etag

		request = urllib.request.Request(url, headers=headers)
		try:
			response = urllib.request.urlopen(request, cafile=certifi.where(), timeout=timeout)
		
		except urllib.error.HTTPError as error:
			if error.code == 304:
				return cached_response[url]
			raise error

		result = json.load(response)

		if etag := response.headers.get('Etag'):
			cached_etag[url] = etag
			cached_response[url] = result

		return result

	result = await core.run_in_executor(blocking)
	return result

def removeprefix(text: str, prefix: str):
	return text[text.startswith(prefix) and len(prefix):]

class GitInstaller(dap.AdapterInstaller):
	def __init__(self, type: str, repo: str, is_valid_asset: Callable[[str], bool] = lambda asset: asset.endswith('.vsix')):
		self.type = type
		self.repo = repo
		self.is_valid_asset = is_valid_asset

	async def install(self, version: str|None, log: core.Logger):
		releases = await request_json(f'https://api.github.com/repos/{self.repo}/releases')
		for release in releases:
			if release['draft'] or release['prerelease']:
				continue

			for asset in release.get('assets', []):
				if self.is_valid_asset(asset['name']):
					release_version = removeprefix(release['tag_name'], 'v')
					if not version or release_version == version:
						return await vscode.install(self.type, asset['browser_download_url'], log) 

		raise core.Error(f'Unable to find a suitable release in {self.repo}')

	def uninstall(self):
		vscode.uninstall(self.type)

	def configuration_snippets(self):
		return vscode.configuration_snippets(self.type)

	def configuration_schema(self):
		return vscode.configuration_schema(self.type)

	def installed_version(self) -> str|None:
		return vscode.installed_version(self.type)

	def install_path(self) -> str: 
		return vscode.install_path(self.type)

	async def installable_versions(self, log: core.Logger) -> list[str]:
		log.info(f'github {self.repo}')
		try:
			releases = await request_json(f'https://api.github.com/repos/{self.repo}/releases')
			versions: list[str] = []

			for release in releases:
				if release['draft']:
					continue

				for asset in release.get('assets', []):
					if self.is_valid_asset(asset['name']):
						version = removeprefix(release['tag_name'], 'v')
						versions.append(version)
						break

			return versions

		except Exception as e:
			log.error(f'github: {self.repo}: {e}')
			raise e
