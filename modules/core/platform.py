import sys

osx = False
windows = False
linux = False

if sys.platform == "linux" or sys.platform == "linux2":
	linux = True
elif sys.platform == "darwin":
	osx = True
elif sys.platform == "win32":
	windows = True