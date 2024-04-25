from __future__ import annotations
from ...import core
from . import vscode
from . import request

class OpenVsxInstaller(vscode.AdapterInstaller):
	def __init__(self, type: str, repo: str):
		self.type = type
		self.repo = repo

	async def install(self, version: str|None, log: core.Logger):
		version = version or 'latest'
		response = await request.json(f'https://open-vsx.org/api/{self.repo}/{version}')
		url = response['files']['download']
		await self.install_vsix(url, log=log)

	async def installable_versions(self, log: core.Logger) -> list[str]:
		try:
			response = await request.json(f'https://open-vsx.org/api/{self.repo}/latest')
			versions: dict = response['allVersions']
			del versions['latest']
			return list(versions.keys())

		except Exception as e:
			log.error(f'openvsx: {self.repo}: {e}')
			raise e
