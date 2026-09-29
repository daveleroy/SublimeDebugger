from __future__ import annotations
from ...import dap
from .adapter_installer_vscode import VSCodeAdapterInstaller
from . import request

import sublime


def _openvsx_platform() -> str | None:
	platform = sublime.platform()
	arch = sublime.arch()

	platform_map = {
		('osx', 'x64'): 'darwin-x64',
		('osx', 'arm64'): 'darwin-arm64',
		('windows', 'x64'): 'win32-x64',
		('windows', 'arm64'): 'win32-arm64',
		('linux', 'x64'): 'linux-x64',
		('linux', 'arm64'): 'linux-arm64',
	}
	return platform_map.get((platform, arch))


class OpenVsxInstaller(VSCodeAdapterInstaller):
	def __init__(self, type: str, repo: str):
		self.type = type
		self.repo = repo

	async def install(self, version: str|None, log: dap.Console):
		version = version or 'latest'
		response = await request.json(f'https://open-vsx.org/api/{self.repo}/{version}')

		if downloads := response.get('downloads'):
			platform_key = _openvsx_platform()
			if not platform_key or platform_key not in downloads:
				available = ', '.join(downloads.keys())
				raise dap.Error(f'This adapter is not available for this platform ({platform_key or "unknown"}). Available platforms: {available}')

			url = downloads[platform_key]
		else:
			url = response['files']['download']

		await self.install_vsix(url, log=log)

	async def installable_versions(self, log: dap.Console) -> list[str]:
		try:
			response = await request.json(f'https://open-vsx.org/api/{self.repo}/latest')
			versions: dict = response['allVersions']
			del versions['latest']
			return list(versions.keys())

		except Exception as e:
			log.error(f'openvsx: {self.repo}: {e}')
			raise e
