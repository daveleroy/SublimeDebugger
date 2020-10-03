from .. import core

from .render import *

from .html import div, span, text, icon, click, code
from .style import css

from .layout import *
from .image import *
from .input import *
from .align import *

_update_timer = None #type: Optional[Timer]


def startup() -> None:
	Images.shared = Images()
	global _update_timer
	_update_timer = Timer(update, 0.25, True)


def shutdown() -> None:
	if _update_timer:
		_update_timer.dispose()

	# perform one final render to clear up phantoms
	perform_render()
