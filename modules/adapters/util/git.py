from __future__ import annotations
from typing import Callable

from ...import core

from .import vscode
from .import request

class GitInstaller(vscode.AdapterInstaller):
	def __init__(self, type: str, repo: str, is_valid_asset: Callable[[str], bool] = lambda asset: asset.endswith('.vsix')):
		self.type = type
		self.repo = repo
		self.is_valid_asset = is_valid_asset

	async def install(self, version: str|None, log: core.Logger):
		releases = await request.json(f'https://api.github.com/repos/{self.repo}/releases')
		for release in releases:
			is_release = not release['draft'] and not release['prerelease']
			release_version = removeprefix(release['tag_name'], 'v')

			for asset in release.get('assets', []):
				if self.is_valid_asset(asset['name']):
					if not version and is_release or version == release_version:
						return await self.install_from_asset(asset['browser_download_url'], log) 

		raise core.Error(f'Unable to find a suitable release in {self.repo}')

	async def installable_versions(self, log: core.Logger) -> list[str]:
		log.info(f'{self.type}: github {self.repo}')
		try:
			releases = await request.json(f'https://api.github.com/repos/{self.repo}/releases')
			versions: list[str] = []

			for release in releases:
				is_release = not release['draft'] and not release['prerelease']
				if not is_release:
					continue

				for asset in release.get('assets', []):
					if self.is_valid_asset(asset['name']):
						release_version = removeprefix(release['tag_name'], 'v')
						versions.append(release_version)
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
		releases = await request.json(f'https://api.github.com/repos/{self.repo}/releases')
		for release in releases:
			is_release = not release['draft'] and not release['prerelease']
			release_version = removeprefix(release['tag_name'], 'v')

			if not version and is_release or version == release_version:
				return await self.install_from_asset(release['zipball_url'], log) 

		raise core.Error(f'Unable to find a suitable release in {self.repo}')

	async def installable_versions(self, log: core.Logger) -> list[str]:
		log.info(f'{self.type}: github {self.repo}')
		try:
			releases = await request.json(f'https://api.github.com/repos/{self.repo}/releases')
			versions: list[str] = []

			for release in releases:
				is_release = not release['draft'] and not release['prerelease']
				if not is_release:
					continue

				version = removeprefix(release['tag_name'], 'v')
				versions.append(version)

			return versions

		except Exception as e:
			log.error(f'{self.type}: {e}')
			raise e

def removeprefix(text: str, prefix: str):
	return text[text.startswith(prefix) and len(prefix):]