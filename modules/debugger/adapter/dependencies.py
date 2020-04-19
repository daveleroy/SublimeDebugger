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

def get_and_warn_require_node_less_than_or_equal(adapter_type: str, log: core.Logger, max_version: str):
	node_path = get_node_path(adapter_type)
	try: 
		version = subprocess.check_output([node_path, '-v']).strip().decode("utf-8")
		if version_tuple(version) > version_tuple(max_version):
			log.error(f'This adapter may not run on your version of node. It may require a version less than or equal to {max_version}. The version of node found is {version} If you want this issue fixed you can file an issue to the adapter owner.')

	except Exception as e:
		log.error(f'This adapter requires node it looks like you may not have node installed or it is not on your path: {e}\nhttps://nodejs.org/')

	return node_path