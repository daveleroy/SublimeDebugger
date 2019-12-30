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
