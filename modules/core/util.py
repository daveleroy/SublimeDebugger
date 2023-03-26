from __future__ import annotations

import shutil
import zipfile
import os
import sublime

from .log import debug
from .error import Error


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
