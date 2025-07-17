from __future__ import annotations
from typing import TYPE_CHECKING, Dict, TypeVar

from . import api

if TYPE_CHECKING:
	from .configuration import SourceLocation

T = TypeVar('T')
V = TypeVar('V')


class _DefaultDict(Dict[T, V]):
	def __missing__(self, key: str):
		return f'{{{key}}}'


class Error(Exception):
	def __init__(self, message: str, url: str | None = None, urlLabel: str | None = None, source: SourceLocation|None = None):
		super().__init__(message)
		self.message = message
		self.url = url
		self.source = source
		self.urlLabel = urlLabel

	@staticmethod
	def from_message(message: api.Message):
		# why on earth does the optional error details have variables that need to be formatted in it????????
		format = message.format or 'No error reason given'
		if message.variables:
			variables: dict[str, str] = _DefaultDict(**(message.variables))
			error_message = format.format_map(variables)
			return Error(error_message, message.url, message.urlLabel)

		return Error(format, message.url, message.urlLabel)


class NoActiveSessionError(Error):
	...
