from __future__ import annotations
from typing import Any

from .import util
from .. import dap
from .. import core

import sublime
import shutil
import os
import subprocess
import shlex
from pathlib import Path

class PythonInstaller(util.GitSourceInstaller):
	async def post_install(self, version: str, log: core.Logger):
		path = self.temporary_install_path()
		debugpy_info = core.json_decode_file(f'{path}/debugpy_info.json')
		try:
			url = debugpy_info['any'][0]['url']
		except Exception:
			url = debugpy_info['any']['url']

		await util.request.download_and_extract_zip(url, f'{path}/debugpy', log=log)


class Python(dap.AdapterConfiguration):

	type = ['debugpy', 'python']
	docs = 'https://github.com/microsoft/vscode-docs/blob/main/docs/python/debugging.md#python-debug-configurations-in-visual-studio-code'

	installer = PythonInstaller(
		type = 'debugpy',
		repo ='microsoft/vscode-python-debugger'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		if configuration.request == 'attach':
			connect = configuration.get('connect')
			if connect:
				host = connect.get('host', 'localhost')
				port = connect.get('port')
				return dap.SocketTransport(host, port)

			port = configuration.get('port')
			if port:
				host = configuration.get('host', 'localhost')
				return dap.SocketTransport(host, port)

			if not configuration.get('listen') and not configuration.get('processId'):
				sublime.error_message('Warning: Check your debugger configuration.\n\n"attach" requires "connect", "listen" or "processId".\n\nIf they contain a $variable that variable may not have existed.')

		install_path = self.installer.install_path()

		python = configuration.get('pythonPath') or configuration.get('python')

		if not python:
			if 'cwd' in configuration:
				venv = self.get_venv(log, Path(configuration['cwd']))
			elif 'program' in configuration:
				venv = self.get_venv(log, Path(configuration['program']).parent)
			else:
				venv = None

			if venv:
				python, folder = venv
				log.info('Detected virtual environment for `{}`'.format(folder))
			elif shutil.which('python3'):
				python = shutil.which('python3')
			else:
				python = shutil.which('python')

		if not python:
			raise core.Error('Unable to find `python3` or `python`')

		log.info('Using python `{}`'.format(python))

		return dap.StdioTransport([
			f'{python}',
			f'{install_path}/debugpy/debugpy/adapter',
		])

	async def on_custom_event(self, session: dap.Session, event: str, body: Any):
		if event == 'debugpyAttach':
			configuration = dap.Configuration.from_json(body, -1)
			configuration_expanded = dap.ConfigurationExpanded(configuration, session.configuration.variables)
			await session.debugger.launch(session.breakpoints, self, configuration_expanded, parent=session)
		else:
			core.info(f'event not handled `{event}`')

	# TODO: patch in env since python seems to not inherit it from the adapter process.
	# async def configuration_resolve(self, configuration: dap.ConfigurationExpanded):
	# 	...

	@property
	def configuration_snippets(self) -> list[dict[str, Any]]:
		return [
			{
				'label': 'Python: Current File',
				'body': {
					'name': 'Python: Current File',
					'type': 'python',
					'request': 'launch',
					'program': '\\${file}'
				}
			},
			{
				'label': 'Python: Attach using process id',
				'body': {
					'name': 'Python: Attach using process id',
					'type': 'python',
					'request': 'launch',
					'processId': '${1:process id}'
				}
			}
		]

	def get_venv(self, log: core.Logger, start: Path) -> tuple[Path, Path]|None:
		"""
		Searches a venv in `start` and all its parent directories.
		"""
		resolved = start.resolve()
		for folder in [resolved] + list(resolved.parents):
			python_path = self.resolve_python_path_from_venv_folder(log, folder)
			if python_path:
				return python_path, folder
		return None

	def resolve_python_path_from_venv_folder(self, log: core.Logger, folder: Path) -> Path|None:
		"""
		Resolves the python binary from venv.
		"""

		def binary_from_python_path(path: Path) -> Path|None:
			if sublime.platform() == 'windows':
				binary_path = path / 'Scripts' / 'python.exe'
			else:
				binary_path = path / 'bin' / 'python'

			return binary_path if os.path.isfile(binary_path) else None


		# Config file, venv resolution command, post-processing
		venv_config_files = [
			('Pipfile', ['pipenv', '--py'], None),
			('poetry.lock', ['poetry', 'env', 'info', '-p'], binary_from_python_path),
			('.python-version', ['pyenv', 'which', 'python'], None),
		]

		if sublime.platform() == 'windows':
			# do not create a window for the process
			startupinfo = subprocess.STARTUPINFO()  # type: ignore
			startupinfo.wShowWindow = subprocess.SW_HIDE  # type: ignore
			startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore
		else:
			startupinfo = None  # type: ignore

		for config_file, command, post_processing in venv_config_files:
			full_config_file_path = folder / config_file
			if os.path.isfile(full_config_file_path):
				try:
					python_path = Path(subprocess.check_output(
						command, cwd=folder, startupinfo=startupinfo, universal_newlines=True
					).strip())
					return post_processing(python_path) if post_processing else python_path
				except FileNotFoundError:
					log.warn(f'{config_file} detected but {command[0]} not found')
				except subprocess.CalledProcessError:
					log.warn(f'{config_file} detected but {" ".join(map(shlex.quote, command))} exited with non-zero exit status')

		# virtual environment as subfolder in project
		for file in folder.iterdir():
			maybe_venv_path = folder / file
			if os.path.isfile(maybe_venv_path / 'pyvenv.cfg'):
				binary = binary_from_python_path(maybe_venv_path)
				if binary is not None:
					return binary  # found a venv

		return None
