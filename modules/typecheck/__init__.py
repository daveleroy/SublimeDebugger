# this is for mypy
# we add our own stubs so we don't need to escape types

from typing import *

try:
	from typing_extensions import Protocol #type: ignore
except:
	from .typing import Protocol #type: ignore
