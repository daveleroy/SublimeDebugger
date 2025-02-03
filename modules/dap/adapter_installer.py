from __future__ import annotations
from typing import Any
import os
from .. import core


class AdapterInstaller:
	type: str

	async def perform_install(self, version: str, log: core.Logger):
		self.remove()
		core.debugger_storage_path(ensure_exists=True)
		core.make_directory(self.temporary_install_path())

		await self.install(version, log)
		await self.post_install(version, log)

		os.rename(self.temporary_install_path(), self.install_path())

	async def install(self, version: str, log: core.Logger) -> None: ...

	async def post_install(self, version: str, log: core.Logger) -> None: ...

	def remove(self) -> None:
		core.remove_file_or_dir(self.temporary_install_path())
		core.remove_file_or_dir(self.install_path())

	def temporary_install_path(self) -> str:
		return os.path.join(core.debugger_storage_path(), f'{self.type}.tmp')

	def install_path(self) -> str:
		return os.path.join(core.debugger_storage_path(), f'{self.type}')

	def installed_version(self) -> str | None:
		return '1.0.0'

	# note versions that include '(' are not installed unless explicity selected from the installable versions menu
	# this supports tags like (prerelease) / (draft)
	async def installable_versions(self, log: core.Logger) -> list[str]:
		return []

	async def installable_versions_with_default(self, log: core.Logger) -> tuple[str, list[str]]:
		versions = await self.installable_versions(log)
		if not versions:
			raise core.Error('No installable versions')

		versions_without_tags = filter(lambda v: not '(' in v, versions)
		version = next(versions_without_tags) or versions[0]
		return version, versions

	def configuration_snippets(self, schema_type: str | None = None) -> list[dict[str, Any]]:
		return []

	def configuration_schema(self, schema_type: str | None = None) -> dict[str, Any]:
		return {}
