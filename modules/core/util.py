from __future__ import annotations

import shutil
from typing import Any, Callable
import zipfile
import os
import sublime
import time

from .log import debug
from .error import Error

from .asyncio import (
	Future,
	CancelledError,

	call_later,
	call_soon,
	delay,
	run,
	run_in_executor,

	gather,
	gather_results,
)


_current_package = __package__.split('.', 1)[0]
_current_package_path = os.path.join(sublime.packages_path(), _current_package)

def debugger_storage_path(ensure_exists: bool = False):
	"""
	This is taken from LSP

	The "Package Storage" is a way to store server data without influencing the behavior of Sublime Text's "catalog".
	Its path is '$DATA/Package Storage', where $DATA means:

	- on macOS: ~/Library/Application Support/Sublime Text
	- on Windows: %AppData%/Sublime Text/Roaming
	- on Linux: $XDG_CONFIG_DIR/sublime-text
	"""
	package_storage_path = os.path.abspath(os.path.join(sublime.cache_path(), '..', 'Package Storage'))

	package_path = os.path.join(package_storage_path, 'Debugger')
	if ensure_exists:
		make_directory(package_storage_path)
		make_directory(package_path)

	return package_path


def package_path(*components: str) -> str:
	if components:
		return os.path.join(_current_package_path, *components)
	return _current_package_path

def package_path_relative(component: str) -> str:
	# WARNING!!! dont change to os.path.join sublime doesn't like back slashes in add_region? and other places?
	return f'Packages/{_current_package}/{component}'


class stopwatch:
	def __init__(self, prefix: str = '') -> None:
		self.ts = time.time()
		self.prefix = prefix

	def __call__(self, postfix='') -> None:
		self.print(postfix)

	def print(self, postfix=''):
		te = time.time()
		print ('%s: %2.2f ms %s' %  (self.prefix.rjust(8), (te - self.ts) * 1000, postfix))

	def elapsed(self):
		te = time.time()
		return (te - self.ts) * 1000

class timer:
	def __init__(self, callback: Callable[[], Any], interval: float, repeat: bool = False) -> None:
		self.interval = interval
		self.callback = callback
		self.cancelable = call_later(interval, self.on_complete)
		self.repeat = repeat

	def schedule(self) -> None:
		self.cancelable = call_later(self.interval, self.on_complete)

	def on_complete(self) -> None:
		self.callback()
		if self.repeat:
			self.schedule()

	def dispose(self) -> None:
		self.cancelable.cancel()

def symlink(origin: str, destination: str):
	try:
		os.symlink(origin, destination)

	# try not to delete real stuff if we can avoid it
	except FileExistsError:
		if os.path.islink(destination):
			os.remove(destination)
			os.symlink(origin, destination)
			return
		if os.path.isdir(destination) and len(os.listdir(destination)) == 0:
			os.remove(destination)
			os.symlink(origin, destination)
			return
		raise

def write(path: str, data: str, overwrite_existing=False):
	if not overwrite_existing and os.path.exists(path):
		return

	with open(path, 'w') as f:
		f.write(data)

def make_directory(path: str):
	try:
		os.mkdir(path)
	except FileExistsError: ...

def remove_file_or_dir(path: str):
	if not os.path.exists(path):
		return

	if os.path.isdir(path):
		debug(f'removing previous directory: {path}')
		shutil.rmtree(_abspath_fix(path))

	elif os.path.isfile(path):
		debug(f'removing previous file: {path}')
		os.remove(path)

	else:
		raise Error('Unexpected file type')


# Fix for long file paths on windows not being able to be extracted from a zip file
# Fix for extracted files losing their permission flags
# https://stackoverflow.com/questions/40419395/python-zipfile-extractall-ioerror-on-windows-when-extracting-files-from-long-pat
# https://stackoverflow.com/questions/39296101/python-zipfile-removes-execute-permissions-from-binaries
class ZipFile(zipfile.ZipFile):
	def _path(self, path, encoding=None):
		return _abspath_fix(path)

	def _extract_member(self, member, targetpath, pwd):
		if not isinstance(member, zipfile.ZipInfo):
			member = self.getinfo(member)

		targetpath = self._path(targetpath)
		ret_val = zipfile.ZipFile._extract_member(self, member, targetpath, pwd) #type: ignore

		attr = member.external_attr >> 16
		if attr != 0:
			os.chmod(ret_val, attr)
		return ret_val

def _abspath_fix(path):
	if sublime.platform() == 'windows':
		path = os.path.abspath(path)
		if path.startswith('\\\\'):
			path = '\\\\?\\UNC\\' + path[2:]
		else:
			path = '\\\\?\\' + path
	return path
