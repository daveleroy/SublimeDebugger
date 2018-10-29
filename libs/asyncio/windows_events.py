"""Selector and proactor event loops for Windows."""

from . import events
from . import selector_events
from . import windows_utils

__all__ = ['SelectorEventLoop',
           'DefaultEventLoopPolicy',
           ]

class _WindowsSelectorEventLoop(selector_events.BaseSelectorEventLoop):
    """Windows version of selector event loop."""

    def _socketpair(self):
        return windows_utils.socketpair()


SelectorEventLoop = _WindowsSelectorEventLoop


class _WindowsDefaultEventLoopPolicy(events.BaseDefaultEventLoopPolicy):
    _loop_factory = SelectorEventLoop


DefaultEventLoopPolicy = _WindowsDefaultEventLoopPolicy
