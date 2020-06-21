from ...import core
from ...typecheck import*
from ..util import get_debugger_setting

import subprocess

def version_tuple(v):
	print(v)
	return tuple(v.split("."))

def get_node_path(adapter_type: str):
	path = get_debugger_setting(f'{adapter_type}.node')
	if path:
		return path

	path = get_debugger_setting('node')
	if path:
		return path

	return 'node'

def get_and_warn_require_node(adapter_type: str, log: core.Logger):
	node_path = get_node_path(adapter_type)
	try:
		subprocess.check_output([node_path, '-v'])
	except Exception as e:
		log.error(f'This adapter requires node it looks like you may not have node installed or it is not on your path: {e}. \nhttps://nodejs.org/')

	return node_path
