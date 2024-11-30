from __future__ import annotations
import os
from re import sub
import stat

import sublime

from .. import dap
from .. import core
from . import util
from .util import request

class CSharpInstaller(util.GitSourceInstaller):
	HOSTS_PLATFORMS = {
		'windows': 'win32',
		'linux': 'linux',
		'osx': 'osx',
	}

	HOST_ARCHS = {
		'x64'  : 'x86_64',
		'x32'  : 'x86',
		'arm64': 'arm64'
	}

	# look through the package.json to install netcoredbg
	async def post_install(self, version: str, log: core.Logger):
		path = self.temporary_install_path()
		data = core.json_decode_file(f'{path}/package.json')

		log.info(data['runtimeDependencies'])

		for dep in data['runtimeDependencies']:
			if dep['id'] != 'Debugger':
				continue

			platforms = dep['platforms']
			architectures = dep['architectures']

			url = dep['url']
			if self.platform_check(platforms, architectures):
				return await self.download_and_unarchive(url, os.path.join(path , 'runtimeDependencies'), log=core.stdio)

		raise core.Error('Unable to find suitable netcoredbg runtime dependency')

	async def download_and_unarchive(self, url: str, path: str, log: core.Logger):
		log.info('Downloading {}'.format(url))
		if (url.find('.tar.gz') >= 0):
			return await request.download_and_extract_targz(url, path, log=core.stdio)
		else:
			return await request.download_and_extract_zip(url, path, log=core.stdio)

	def platform_check(self, platforms, archs):
		return self.HOSTS_PLATFORMS[sublime.platform()] in platforms and self.HOST_ARCHS[sublime.arch()] in archs


class CSharp(dap.AdapterConfiguration):
	type = ['coreclr', 'netcoredbg']
	docs = 'https://github.com/muhammadsammy/free-vscode-csharp/blob/master/debugger.md'
	development = True

	installer = CSharpInstaller('coreclr', 'muhammadsammy/free-vscode-csharp')

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		install_path = self.installer.install_path()
		executable_path = 'netcoredbg.exe' if sublime.platform() == 'windows' else 'netcoredbg/netcoredbg'

		args = []
		if 'pipeTransport' in configuration:
			pipe_transport = configuration.get('pipeTransport')
			if isinstance(pipe_transport, dict):
				if 'debuggerArgs' in pipe_transport:
					debugger_args = pipe_transport.get('debuggerArgs')
					if isinstance(debugger_args, list):
						args.extend(debugger_args)
					else:
						raise TypeError("debuggerArgs should be a list")
				else:
					args.extend(['--interpreter=vscode', '--'])

				if 'pipeProgram' in pipe_transport:
					args.append(pipe_transport.get('pipeProgram'))
				if 'pipeArgs' in pipe_transport:
					pipe_args = pipe_transport.get('pipeArgs')
					if isinstance(pipe_args, list):
						args.extend(pipe_args)
					else:
						raise TypeError("pipeArgs should be a list")
			else:
				raise TypeError("pipeTransport should be a dict")
		else:
			args = ['--interpreter=vscode']

		command = [os.path.join(install_path, 'runtimeDependencies', executable_path), ]
		command.extend(args)

		return dap.StdioTransport(command, stderr=log.error)
