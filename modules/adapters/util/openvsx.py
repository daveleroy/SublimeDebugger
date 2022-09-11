from __future__ import annotations
from .git import request_json, removeprefix
from ...libs.semver import semver
from ...import core
from ...import dap
from . import vscode

class OpenVsxInstaller(dap.AdapterInstaller):
	def __init__(self, type: str, repo: str):
		self.type = type
		self.repo = repo

	async def install(self, version: str|None, log: core.Logger):
		version = version or 'latest'
		response = await request_json(f'https://open-vsx.org/api/{self.repo}/{version}')
		url = response['files']['download']
		await vscode.install(self.type, url, log)

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
		log.info(f'openvsx: {self.repo}')
		try:
			response = await request_json(f'https://open-vsx.org/api/{self.repo}/latest')
			versions: dict = response['allVersions']
			del versions['latest']
			return list(versions.keys())

		except Exception as e:
			log.error(f'openvsx: {self.repo}: {e}')
			raise e
