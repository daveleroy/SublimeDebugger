
from debug.core.typecheck import (
	Optional
)

import sublime
import os
import json

FILE_LOG = 'debug.log'
FILE_BREAKPOINTS = 'breakpoints_data.json'
FILE_SETTINGS = 'debug.sublime-settings'
FILE_PERSISTANCE = 'persistance.json'

def package_path(path: str) -> str:
	return "{}/debug/{}".format(sublime.packages_path(), path)

# _already_saving_breakpoints = False

# ''' Saves breakoints at some point in the future...'''
# def save_breakpoints(main: Main) -> None:
# 	if _already_saving_breakpoints:
# 		return 


_all_data = None #type: Optional[dict]

def save_data() -> None:
	assert not _all_data is None
	data = json.dumps(_all_data)
	file = open(package_path(FILE_PERSISTANCE), 'w+')
	contents = file.write(data)
	file.close()

def persisted_for_project(project_name: str) -> dict:
	global _all_data
	try:
		file = open(package_path(FILE_PERSISTANCE), 'r+')
		contents = file.read()
		file.close()
		_all_data = json.loads(contents)
	except FileNotFoundError:
		_all_data = {}
	assert not _all_data is None
	project_data = _all_data.setdefault(project_name, {})
	return project_data

