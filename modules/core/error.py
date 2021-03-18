from __future__ import annotations

class Error(Exception):
	def __init__(self, format: str):
		super().__init__(format)
