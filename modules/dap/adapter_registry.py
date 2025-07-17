from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar, Type

from .. import core



if TYPE_CHECKING:
	from .error import Error
	from .adapter import Adapter
	from .debugger import Console


class AdapterRegistery(type):
	def __new__(cls, name, bases, dct):
		kclass = type.__new__(cls, name, bases, dct)
		if bases:
			AdapterRegistery._register(kclass())

		return kclass

	registered: ClassVar[list[Adapter]] = []
	registered_types: ClassVar[dict[str | Type[Adapter], Adapter]] = {}

	@staticmethod
	def _register(adapter: Adapter):
		if not adapter.type:
			return

		from .adapter import Adapter

		Adapter.registered.append(adapter)
		for type in adapter.types:
			Adapter.registered_types[type] = adapter

	@staticmethod
	def get(type: str | Type[Adapter]) -> Adapter:
		from .adapter import Adapter

		if adapter := Adapter.registered_types.get(type):
			return adapter

		raise Error(f'Unable to find debug adapter with the type name "{type}"')

	@staticmethod
	@core.run
	async def install_adapter(console: Console, adapter: Adapter, version: str | None) -> None:
		console.log('group-start', f'{core.platform.unicode_unchecked_sigil} Installing {adapter.name}')

		try:
			if version is None:
				version, _ = await adapter.installer.installable_versions_with_default(console)

			await adapter.installer.perform_install(version, console)

		except Exception as error:
			console.log('group-end', None)
			console.error(f'{core.platform.unicode_checked_sigil} Failed: {error}')
			raise error

		from .schema import generate_lsp_json_schema

		generate_lsp_json_schema()

		console.log(
			'success',
			f'Successfully installed {adapter.name}. Checkout the documentation for this adapter {adapter.docs}',
		)
		console.log('group-end', f'{core.platform.unicode_checked_sigil} Finished')
