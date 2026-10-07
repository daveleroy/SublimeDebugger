from __future__ import annotations

from ...settings import Settings, SettingsRegistery
from ...import dap

import socket
import shutil

def version_tuple(v: str):
	return tuple(v.split('.'))

def get_node_path(adapter_type: str|list[str]) -> str:
	return Settings.node or shutil.which('node') or 'node'

async def get_and_warn_require_node(adapter_type: str|list[str], log: dap.Console):
	node_path = get_node_path(adapter_type)
	# max_version = 'v13.0.0'

	try:
		version = (await dap.Process.check_output([node_path, '-v'])).strip().decode('utf-8')
		log('transport', f'-- node: version={version}')
		# if version and version_tuple(version) >= version_tuple(max_version):
		# 	log.error(f'This adapter may not run on your version of node. It may require a version less than {max_version}. The version of node found is {version}.')

	except Exception as e:
		log.error(f'This adapter requires node it looks like you may not have node installed or it is not on your path: {e}. \nhttps://nodejs.org/')

	return node_path

def get_open_port() -> int:
	with socket.socket() as sock:
		sock.bind(('localhost', 0))
		port = sock.getsockname()[1]
		return port

def require_package(package: str):
	if not SettingsRegistery.is_package_installed(package):
		raise dap.Error(f'{package} must be installed and enabled')
