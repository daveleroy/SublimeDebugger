from __future__ import annotations

class Error(Exception):
	message = 'Unknown Error Occured'

	def __init__(self, message: str|None = None):
		super().__init__(message or self.message or 'Unknown Error Occured')
