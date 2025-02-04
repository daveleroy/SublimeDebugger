from __future__ import annotations
from typing import TYPE_CHECKING, Awaitable
from .. import core
from . import dap

if TYPE_CHECKING:
	from ..breakpoints import Session


class Thread:
	def __init__(self, session: Session, id: int, name: str, stopped: bool):
		self.session = session
		self.id = id
		self.name = name
		self.stopped = stopped
		self.stopped_reason = ''
		self.stopped_event: dap.StoppedEvent | None = None
		self._children: core.Future[list[dap.StackFrame]] | None = None

	def __str__(self) -> str:
		return f'{self.id}: {self.name}'

	def has_children(self) -> bool:
		return self.stopped

	def children(self) -> Awaitable[list[dap.StackFrame]]:
		if not self.stopped:
			raise core.Error('Cannot get children of thread that is not stopped')

		if self._children:
			return self._children
		self._children = core.run(self.session.stack_trace(self.id))
		return self._children

	def set_stopped(self, event: dap.StoppedEvent | None):
		self._children = None  # children are no longer valid

		self.stopped = True

		if event:
			description = event.description
			text = event.text
			reason = event.reason

			if description and text:
				stopped_text = 'Stopped: {}: {}'.format(description, text)
			elif text or description or reason:
				stopped_text = 'Stopped: {}'.format(text or description or reason)
			else:
				stopped_text = 'Stopped'

			self.stopped_reason = stopped_text
			self.stopped_event = event

	def set_continued(self, event: dap.ContinuedEvent | None):
		self.stopped = False
		self.stopped_reason = ''
		self.stopped_event = None
