
# this is for mypy we want typing for mypy but sublime doesnt have it
# we add our own stubs so we don't need to escape types
try:
	from typing import *
except:
	from .typing import * #type: ignore