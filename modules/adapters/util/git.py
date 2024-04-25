from __future__ import annotations
from typing import Callable
from ...settings import Setting

from ...import core

from .import vscode
from .import request

import string


github_personal_access_token = Setting['str|None'](
	key='github_personal_access_token',
	default=None,
	description='Personal access token used for github api requests. If you are testing installing adapters you may need to set this to have higher api limits if you are getting 429 errors.'
)

def headers():
	return {
		'Authorization': f'Bearer {github_personal_access_token.value}'
	}\
	if github_personal_access_token.value else {}

class GitInstaller(vscode.AdapterInstaller):
	def __init__(self, type: str, repo: str, is_valid_asset: Callable[[str], bool] = lambda asset: asset.endswith('.vsix')):
		self.type = type
		self.repo = repo
		self.is_valid_asset = is_valid_asset

	async def install(self, version: str, log: core.Logger):
		releases = await request.json(f'https://api.github.com/repos/{self.repo}/releases', headers=headers())
		for release in releases:
			if version != version_from_release(release):
				continue

			for asset in release.get('assets', []):
				if self.is_valid_asset(asset['name']):
					await self.install_vsix(asset['browser_download_url'], log=log)
					return

		raise core.Error(f'Unable to find a suitable release in {self.repo}')

	async def installable_versions(self, log: core.Logger) -> list[str]:
		try:
			releases = await request.json(f'https://api.github.com/repos/{self.repo}/releases', headers=headers())
			versions: list[str] = []

			for release in releases:
				version = version_from_release(release)
				if not version:
					continue

				for asset in release.get('assets', []):
					if self.is_valid_asset(asset['name']):
						versions.append(version)
						break

			return versions

		except Exception as e:
			log.error(f'{self.type}: {e}')
			raise e


class GitSourceInstaller(vscode.AdapterInstaller):
	def __init__(self, type: str, repo: str):
		self.type = type
		self.repo = repo

	async def install(self, version: str|None, log: core.Logger):
		releases = await request.json(f'https://api.github.com/repos/{self.repo}/releases', headers=headers())
		for release in releases:
			if version == version_from_release(release):
				await self.install_source(release['zipball_url'], log=log)
				return

		raise core.Error(f'Unable to find a suitable release in {self.repo}')

	async def installable_versions(self, log: core.Logger) -> list[str]:
		try:
			releases = await request.json(f'https://api.github.com/repos/{self.repo}/releases', headers=headers())
			versions: list[str] = []

			for release in releases:
				if version := version_from_release(release):
					versions.append(version)

			return versions

		except Exception as e:
			log.error(f'{self.type}: {e}')
			raise e

def version_from_release(release: core.JSON):
	# remove anything that isn't a number from the start of a tag
	# lots of tags include a prefix like v
	version: str = release.tag_name
	version = version.lstrip(string.punctuation + string.ascii_letters)

	if release.draft:
		return f'{version} (draft)'

	if release.prerelease:
		return f'{version} (prerelease)'

	return version
