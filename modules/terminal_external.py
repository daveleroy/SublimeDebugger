# The code in this file was modified from https://github.com/microsoft/vscode/blob/master/src/vs/workbench/contrib/externalTerminal/node/externalTerminalService.ts

# MIT License

# Copyright (c) 2015 - present Microsoft Corporation

# All rights reserved.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations
from .typecheck import *

from .import core

import subprocess
import os
import sublime


class ExternalTerminal(Protocol):
	def __init__(self, title: str, cwd: str, commands: list[str], env: dict[str, str|None]):
		...

	def dispose(self):
		...


# requires https://packagecontrol.io/packages/Terminus
class ExternalTerminalTerminus(ExternalTerminal):
	id = 0

	def __init__(self, title: str, cwd: str, commands: list[str], env: dict[str, str|None]):
		self.window = sublime.active_window()
		self.tag = 'sublime_debugger_{}'.format(ExternalTerminalTerminus.id)
		ExternalTerminalTerminus.id += 1
		self.window.run_command('terminus_open', {
			'title': title,
			'cwd': cwd,
			'cmd': commands,
			'env': env,
			'auto_close': False,
			'tag': self.tag,
			'pre_window_hooks': [
				['debugger_console_layout_pre_window_hooks', {}],
			],
			'post_view_hooks': [
				['debugger_console_layout_post_view_hooks', {}],
			],
		})

	def dispose(self):
		for view in self.window.views():
			if view.settings().get("terminus_view.tag") == self.tag:
				view.close()


class ExternalTerminalMacDefault(ExternalTerminal):
	OSX_TERMINAL_SCRIPT = os.path.join(os.path.dirname(__file__), 'libs', 'terminal_scripts', 'TerminalHelper.scpt')
	#OSX_ITERM_SCRIPT = os.path.join(os.path.dirname(__file__), 'iTermHelper.scpt')

	def __init__(self, title: str, cwd: str, commands: list[str], env: dict[str, str|None]):
		args = [
			'osascript',
			ExternalTerminalMacDefault.OSX_TERMINAL_SCRIPT,
			'-t', title,
		]
		if cwd:
			args.append('-w')
			args.append(cwd)

		for command in commands:
			args.append('-a')
			args.append(command)

		for key, value in env.items():
			if value is None:
				args.append('-u')
				args.append(key)
			else:
				args.append('-e')
				args.append('{}={}'.format(key, value))

		subprocess.check_call(args)

	def dispose(self):
		...

# modified from https://github.com/microsoft/vscode/blob/master/src/vs/workbench/contrib/externalTerminal/node/externalTerminalService.ts
class ExternalTerminalWindowsDefault(ExternalTerminal):
	def __init__(self, title: str, cwd: str, commands: list[str], env: dict[str, str|None]):
		if core.platform.is_64:
			exec = 'C:\\Windows\\Sysnative\\cmd.exe'
		else:
			exec = 'C:\\Windows\\System32\\cmd.exe'

		args_string = '" "'.join(commands)
		command = '""{}" & pause"'.format(args_string) # use '|' to only pause on non-zero exit code

		args = [
			'/c', 'start', title, '/wait', exec, '/c', command
		]

		# take process env variables and add or remove items
		cmd_env = os.environ.copy()
		for key, value in env.items():
			if value is None:
				try:
					del cmd_env[key]
				except KeyError:
					pass
			else:
				cmd_env[key] = value

		subprocess.check_call(['cmd.exe'] + args, cwd=cwd, env=cmd_env)

	def dispose(self):
		...

# export class LinuxExternalTerminalService implements IExternalTerminalService {
# 	public _serviceBrand: undefined;

# 	private static readonly WAIT_MESSAGE = nls.localize('press.any.key', "Press any key to continue...");

# 	constructor(
# 		@optional(IConfigurationService) private readonly _configurationService: IConfigurationService
# 	) { }

# 	public openTerminal(cwd?: string): void {
# 		if (this._configurationService) {
# 			const configuration = this._configurationService.getValue<IExternalTerminalConfiguration>();
# 			this.spawnTerminal(cp, configuration, cwd);
# 		}
# 	}

# 	public runInTerminal(title: string, dir: string, args: string[], envVars: env.IProcessEnvironment, settings: IExternalTerminalSettings): Promise<number | undefined> {

# 		const execPromise = settings.linuxExec ? Promise.resolve(settings.linuxExec) : LinuxExternalTerminalService.getDefaultTerminalLinuxReady();

# 		return new Promise<number | undefined>((resolve, reject) => {

# 			let termArgs: string[] = [];
# 			//termArgs.push('--title');
# 			//termArgs.push(`"${TERMINAL_TITLE}"`);
# 			execPromise.then(exec => {
# 				if (exec.indexOf('gnome-terminal') >= 0) {
# 					termArgs.push('-x');
# 				} else {
# 					termArgs.push('-e');
# 				}
# 				termArgs.push('bash');
# 				termArgs.push('-c');

# 				const bashCommand = `${quote(args)}; echo; read -p "${LinuxExternalTerminalService.WAIT_MESSAGE}" -n1;`;
# 				termArgs.push(`''${bashCommand}''`);	// wrapping argument in two sets of ' because node is so "friendly" that it removes one set...

# 				// merge environment variables into a copy of the process.env
# 				const env = assign({}, process.env, envVars);

# 				// delete environment variables that have a null value
# 				Object.keys(env).filter(v => env[v] === null).forEach(key => delete env[key]);

# 				const options: any = {
# 					cwd: dir,
# 					env: env
# 				};

# 				let stderr = '';
# 				const cmd = cp.spawn(exec, termArgs, options);
# 				cmd.on('error', err => {
# 					reject(improveError(err));
# 				});
# 				cmd.stderr.on('data', (data) => {
# 					stderr += data.toString();
# 				});
# 				cmd.on('exit', (code: number) => {
# 					if (code === 0) {	// OK
# 						resolve(undefined);
# 					} else {
# 						if (stderr) {
# 							const lines = stderr.split('\n', 1);
# 							reject(new Error(lines[0]));
# 						} else {
# 							reject(new Error(nls.localize('linux.term.failed', "'{0}' failed with exit code {1}", exec, code)));
# 						}
# 					}
# 				});
# 			});
# 		});
# 	}

# 	private spawnTerminal(spawner: typeof cp, configuration: IExternalTerminalConfiguration, cwd?: string): Promise<void> {
# 		const terminalConfig = configuration.terminal.external;
# 		const execPromise = terminalConfig.linuxExec ? Promise.resolve(terminalConfig.linuxExec) : LinuxExternalTerminalService.getDefaultTerminalLinuxReady();

# 		return new Promise<void>((c, e) => {
# 			execPromise.then(exec => {
# 				const env = cwd ? { cwd } : undefined;
# 				const child = spawner.spawn(exec, [], env);
# 				child.on('error', e);
# 				child.on('exit', () => c());
# 			});
# 		});
# 	}

# 	private static _DEFAULT_TERMINAL_LINUX_READY: Promise<string>;

# 	public static getDefaultTerminalLinuxReady(): Promise<string> {
# 		if (!LinuxExternalTerminalService._DEFAULT_TERMINAL_LINUX_READY) {
# 			LinuxExternalTerminalService._DEFAULT_TERMINAL_LINUX_READY = new Promise<string>(c => {
# 				if (env.isLinux) {
# 					Promise.all([pfs.exists('/etc/debian_version'), Promise.resolve(process.lazyEnv) || Promise.resolve(undefined)]).then(([isDebian]) => {
# 						if (isDebian) {
# 							c('x-terminal-emulator');
# 						} else if (process.env.DESKTOP_SESSION === 'gnome' || process.env.DESKTOP_SESSION === 'gnome-classic') {
# 							c('gnome-terminal');
# 						} else if (process.env.DESKTOP_SESSION === 'kde-plasma') {
# 							c('konsole');
# 						} else if (process.env.COLORTERM) {
# 							c(process.env.COLORTERM);
# 						} else if (process.env.TERM) {
# 							c(process.env.TERM);
# 						} else {
# 							c('xterm');
# 						}
# 					});
# 					return;
# 				}

# 				c('xterm');
# 			});
# 		}
# 		return LinuxExternalTerminalService._DEFAULT_TERMINAL_LINUX_READY;
# 	}
# }

# /**
#  * tries to turn OS errors into more meaningful error messages
#  */
# function improveError(err: Error): Error {
# 	if ('errno' in err && err['errno'] === 'ENOENT' && 'path' in err && typeof err['path'] === 'string') {
# 		return new Error(nls.localize('ext.term.app.not.found', "can't find terminal application '{0}'", err['path']));
# 	}
# 	return err;
# }

# /**
#  * Quote args if necessary and combine into a space separated string.
#  */
# function quote(args: string[]): string {
# 	let r = '';
# 	for (let a of args) {
# 		if (a.indexOf(' ') >= 0) {
# 			r += '"' + a + '"';
# 		} else {
# 			r += a;
# 		}
# 		r += ' ';
# 	}
# 	return r;
# }