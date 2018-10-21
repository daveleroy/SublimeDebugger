
from .events import *
from .layout import *
from .component import *
from .image import *
from .segment import *
from .table import *
from .button import *
from .label import *
from .input import *
from .render import *

import os

from debug.libs import asyncio 
from debug import core

def startup () -> None:
	Images.shared = Images()
	dir_path = os.path.dirname(os.path.abspath(__file__))
	import_css(dir_path + '/ui.css')
	_start_render()

def shutdown () -> None:
	_stop_render()
	

_rendering = False
def _start_render() -> None:
	_rendering = True
	
	@core.async
	def _run_render() -> core.awaitable[None]:
		while _rendering:
			render()
			yield from asyncio.sleep(0.016)
	core.run(_run_render())

def _stop_render() -> None:
	_rendering = False