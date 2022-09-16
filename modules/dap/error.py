from __future__ import annotations
from ..typecheck import *
from ..import core

from .import dap

Json = Dict[str, Any]

T = TypeVar('T')
V = TypeVar('V')

class _DefaultDict(Dict[T, V]):
	def __missing__(self, key: str):
		return key.join("{}")

class Error(core.Error):
	def __init__(self, message: str, url: str|None = None, urlLabel: str|None = None):
		super().__init__(message)
		self.message = message
		self.url = url
		self.urlLabel = urlLabel

	@staticmethod
	def from_message(message: dap.Message):
		# why on earth does the optional error details have variables that need to be formatted in it????????
		format = message.format or 'No error reason given'
		if message.variables:
			variables: dict[str, str] = _DefaultDict(**(message.variables))
			error_message = format.format_map(variables)
			return Error(error_message, message.url, message.urlLabel)

		return Error(format, message.url, message.urlLabel)


