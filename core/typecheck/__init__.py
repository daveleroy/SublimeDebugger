
# this is for mypy we want typing for mypy but sublime doesnt have it
# we add our own stubs so we don't need to escape types
if False:
	from typing import *
else:
	from .typing import * #type: ignore