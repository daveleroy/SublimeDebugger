# this is for mypy
# we add our own stubs so we don't need to escape types
try:
	from typing import *
except:
	from .typing import * #type: ignore

try:
	from typing_extensions import Protocol
except:
	from .typing import Protocol
