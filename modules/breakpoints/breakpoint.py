from __future__ import annotations

from ..import dap


class Breakpoint:

	name: str
	tag: str

	def __init__(self):
		self._result: dap.Breakpoint|None = None
		self._results: dict[dap.Session, dap.Breakpoint] = {}

	@property
	def description(self) -> str|None:
		if self._result:
			return self._result.message
		return None

	@property
	def verified(self):
		# verified if any result is verified or there are no results yet
		if self._result:
			return self._result.verified
		return not self._results

	def _refresh_verified_status(self):
		# if there is no results then we mark it as "verified" until there are results.
		# otherwise we would need another way to handle the case when there are no debug sessions
		if not self._results:
			self._result = None
			return

		self._result = None

		for result in self._results.values():
			if not self._result:
				self._result = result

			if result.verified:
				self._result = result
				return

	def set_breakpoint_result(self, session: dap.Session, result: dap.Breakpoint):
		self._results[session] = result
		self._refresh_verified_status()

	def clear_breakpoint_result(self, session: dap.Session):
		try: 
			del self._results[session]
			self._refresh_verified_status()
			return True

		except KeyError:
			return False
