from ...typecheck import*
from ...settings import Settings
from ...import core
from ...import dap

import subprocess
import shutil

def version_tuple(v):
	return tuple(v.split('.'))

def get_node_path(adapter_type: str) -> str:
	return Settings.node or shutil.which('node') or 'node'

async def get_and_warn_require_node(adapter_type: str, log: core.Logger):
	node_path = get_node_path(adapter_type)
	# max_version = 'v13.0.0'

	try:
		version = (await dap.Process.check_output([node_path, '-v'])).strip().decode('utf-8')
		# if version and version_tuple(version) >= version_tuple(max_version):
		# 	log.error(f'This adapter may not run on your version of node. It may require a version less than {max_version}. The version of node found is {version}.')

	except Exception as e:
		log.error(f'This adapter requires node it looks like you may not have node installed or it is not on your path: {e}. \nhttps://nodejs.org/')

	return node_path
