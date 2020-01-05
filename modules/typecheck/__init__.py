# this is for mypy
# we add our own stubs so we don't need to escape types
try:
	from typing import *
	from typing_extensions import Protocol #type: ignore
except:
	from .typing import * #type: ignore
