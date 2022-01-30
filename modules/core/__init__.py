from __future__ import annotations

import os

from .core import *
from .sublime import *
from .log import *
from .event import Handle, Event, EventReturning
from . import platform
from .error import Error

from .json import json_encode, json_decode

_current_package = __package__.split('.', 1)[0]
_current_package_path = os.path.join(sublime.packages_path(), _current_package)

def current_package() -> str:
	return _current_package_path

def current_package_name() -> str:
	return _current_package
