from __future__ import annotations

import os
import sublime

from .import util
from .. import dap
from .. import core


ARCHIVES = {
	"windows": {
		"x64": "netcoredbg-win64.zip"
	},
	"linux": {
		"x64": "netcoredbg-linux-amd64.tar.gz",
		"arm64": "netcoredbg-linux-arm64.tar.gz",
	},
	"osx": {
		"x64": "netcoredbg-osx-amd64.tar.gz",
	},
}


def _archive():
	platform = sublime.platform()
	arch = sublime.arch()
	try:
		return ARCHIVES[platform][arch]
	except KeyError:
		raise RuntimeError(f"{platform}-{arch} is not known to be supported by netcoredbg.")


class GithubReleaseInstaller(util.vscode.AdapterInstaller):
	type = 'netcoredbg'

	async def install(self, version: str|None, log: core.Logger):
		archive = _archive()
		url = f'https://github.com/Samsung/netcoredbg/releases/download/{version}/{archive}'

		async def post_download_action():
			install_path = self.install_path()
			log.info(f"Unpacked netcoredbg to: {install_path}")

		await self.install_from_asset(url, log, post_download_action)

	async def installable_versions(self, log: core.Logger):
		return ['3.0.0-1018']


class Netcoredbg(dap.AdapterConfiguration):
	type = 'netcoredbg'
	docs = 'https://github.com/Samsung/netcoredbg/blob/master/README.md#usage'

	installer = GithubReleaseInstaller()

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		install_path = self.installer.install_path()
		print(install_path)
		command = [
			f'{install_path}/netcoredbg/netcoredbg',
			'--interpreter=vscode'
		]
		return dap.StdioTransport(log, command)
