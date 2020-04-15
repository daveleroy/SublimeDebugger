from ...import core
from ...typecheck import*

import subprocess

def version_tuple(v):
	print(v)
	return tuple(v.split("."))

def warn_require_node(log: core.Logger):
	try: 
		subprocess.check_output(['noded', '-v'])
	except Exception as e:
		log.error(f'This adapter requires node it looks like you may not have node installed or it is not on your path: {e}. \nhttps://nodejs.org/')

def warn_require_node_less_than_or_equal(log: core.Logger, max_version: str):
	try: 
		version = subprocess.check_output(['node', '-v']).strip().decode("utf-8")
		if version_tuple(version) > version_tuple(max_version):
			log.error(f'This adapter may not run on your version of node. It may require a version less than or equal to {max_version}. The version of node found is {version} If you want this issue fixed you can file an issue to the adapter owner.')

	except Exception as e:
		log.error(f'This adapter requires node it looks like you may not have node installed or it is not on your path: {e}\nhttps://nodejs.org/')