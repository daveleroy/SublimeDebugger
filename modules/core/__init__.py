from __future__ import annotations

import os

from .core import *
from .sublime import *
from .log import *
from .event import Handle, Event
from . import platform
from .error import Error
from .dispose import Disposables, disposables

_current_package = __package__.split('.', 1)[0]

def current_package() -> str:
	return os.path.join(sublime.packages_path(), _current_package)

def current_package_name() -> str:
	return _current_package
