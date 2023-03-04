from __future__ import annotations
from typing import Any, Awaitable, Callable, Coroutine, Generator, Generic, Iterable, Protocol, TypeVar, overload
from .typing import TypeVarTuple, Unpack, ParamSpec

import sublime
import concurrent


D = TypeVar("D", bound="Disposeable")


class Disposeable(Protocol):
	def dispose(self): ...


class Dispose:
	_dispose: list[Disposeable]|None = None

	def dispose(self):
		if not self._dispose: return

		for _dispose in self._dispose:
			_dispose.dispose()

	def dispose_remove(self, item: Disposeable):
		if not self._dispose: return

		self._dispose.remove(item)
		item.dispose()

	def dispose_add(self, item: Disposeable|list[Disposeable]):
		if not self._dispose:
			self._dispose = []

		if isinstance(item, list):
			for i in item:
				self._dispose.append(i)
		else:
			self._dispose.append(item)



def remove_and_dispose(list: list[D], filter: Callable[[D], bool]):
	remove = []
	for item in list:
		if filter(item):
			remove.append(item)

	for item in remove:
		list.remove(item)
		item.dispose()


def display(msg: 'Any'):
	sublime.error_message('{}'.format(msg))
