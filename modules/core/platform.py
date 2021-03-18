from __future__ import annotations

import sys
import platform

osx = False
windows = False
linux = False

is_64 = platform.machine().endswith('64')

if sys.platform == "linux" or sys.platform == "linux2":
	linux = True
elif sys.platform == "darwin":
	osx = True
elif sys.platform == "win32":
	windows = True

architecture = None
if platform.machine() == 'arm64' or platform.machine() == 'aarch64':
	architecture = 'aarch64'
elif platform.machine() == 'x86_64':
	architecture = 'x86_64'
