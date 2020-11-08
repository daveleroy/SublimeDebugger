from ..typecheck import *
from ..import core
from ..import ui

import sublime
import re


@core.schedule
async def select_process():
	from ..libs import psutil

	list = []
	selected_proc: Any = None

