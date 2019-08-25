import sys

osx = False
windows = False
linux = False

if sys.platform == "linux" or sys.platform == "linux2":
	global linux
	linux = True
elif sys.platform == "darwin":
	global osx
	osx = True
elif sys.platform == "win32":
	global windows
	windows = True