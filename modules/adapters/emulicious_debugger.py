from __future__ import annotations

from . import util
from .. import dap
from .. import core

import sublime
import socket
import subprocess
import os.path

class EmuliciousDebugger(dap.AdapterConfiguration):

	type = 'emulicious-debugger'
	docs = 'https://github.com/Calindro/emulicious-debugger#usage'

	installer = util.GitInstaller(
		type='emulicious-debugger',
		repo='calindro/emulicious-debugger'
	)

	async def start(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		if configuration.get("port") is None:
			raise Exception("The field 'port' is not set. Please check your launch configuration.")
		check_port_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		check_port_socket.settimeout(0.1)
		if check_port_socket.connect_ex((configuration.get("host") or "localhost", configuration.get("port"))) != 0:
			return self.startEmulicious(log, configuration)
		check_port_socket.close()
		return dap.SocketTransport(configuration.get("host") or "localhost", configuration.get("port"))

	def startEmulicious(self, log: core.Logger, configuration: dap.ConfigurationExpanded):
		if configuration.get("request") == 'attach':
			raise Exception("Failed to attach to Emulicious Debugger.\n" +
							"Please make sure that Emulicious is running and Remote Debugging is enabled in Emulicious's Tools menu.")
		emuliciousPath = configuration.get('emuliciousPath')
		cwd = configuration.variables.get('folder')
		startupinfo = None
		if os.name == 'nt':
			startupinfo = subprocess.STARTUPINFO()
			startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		if emuliciousPath is None:
			try:
				subprocess.Popen(["emulicious", "-remotedebug", str(configuration.get("port"))], cwd=cwd, startupinfo=startupinfo)
			except:
				raise Exception("Failed to launch Emulicious Debugger for the following reason:\n" +
								"Could not connect to Emulicious and could not start Emulicious because emuliciousPath is not set.\n" +
								"Please make sure to set emuliciousPath either in the launch configuration of your project settings.")
		else:
			if not os.path.exists(emuliciousPath):
				raise Exception("Failed to launch Emulicious Debugger for the following reason:\n" +
								"The file or folder specified in emuliciousPath does not exist:\n\n" +
								"emuliciousPath: " + emuliciousPath + "\n\n" +
								"Please check your configuration.")
			if os.path.isdir(emuliciousPath):
				emuliciousJar = os.path.join(emuliciousPath, "Emulicious.jar")
				if not os.path.exists(emuliciousJar):
					raise Exception("Failed to launch Emulicious Debugger for the following reason:\n" +
									"The file or folder specified in emuliciousPath does not contain Emulicious.jar:\n\n" +
									"emuliciousPath: " + emuliciousPath + "\n\n" +
									"Please check your configuration.")
				emuliciousPath = emuliciousJar
			if emuliciousPath.endswith(".jar"):
				javaPath = configuration.get("javaPath")
				args = [ "-jar", emuliciousPath, "-remotedebug", str(configuration.get("port")) ]
				try:
					subprocess.Popen([javaPath or "java"] + args, cwd=cwd, startupinfo=startupinfo)
				except:
					if javaPath is not None:
						raise Exception("Failed to launch Emulicious Debugger for the following reason:\n" +
										"Could not start the jar file specified by emuliciousPath with Java specified by javaPath:\n\n" +
										"emuliciousPath: " + emuliciousPath + "\n" +
										"javaPath: " + javaPath + "\n\n" +
										"Please check your configuration.\n" +
										"javaPath should point to the executable of Java (e.g. java.exe).")
					javaPath = os.path.join(os.path.dirname(emuliciousPath), "java", "bin", "java.exe")
					try:
						subprocess.Popen([javaPath] + args, cwd=cwd, startupinfo=startupinfo)
					except:
						raise Exception("Failed to launch Emulicious Debugger for the following reason:\n" +
										"Could not start the jar file specified by emuliciousPath:\n\n" +
										"emuliciousPath: " + emuliciousPath + "\n\n" +
										"Please check your configuration.\n" +
										"You might need to install Java or download Emulicious with Java.\n" +
										"If you already have Java installed, you can specify the path to Java via javaPath in your configuration.")
			else:
				try:
					subprocess.Popen([emuliciousPath, "-remotedebug", str(configuration.get("port"))], cwd=cwd, startupinfo=startupinfo)
				except:
					raise Exception("Failed to launch Emulicious Debugger for the following reason:\n" +
									"Could not start the file specified by emuliciousPath:\n\n" +
									"emuliciousPath: " + emuliciousPath + "\n\n" +
									"Please check your configuration.")

			maxAttempts = 25
			for _ in range(maxAttempts):
				check_port_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				check_port_socket.settimeout(0.1)
				if check_port_socket.connect_ex((configuration.get("host") or "localhost", configuration.get("port"))) == 0:
					check_port_socket.close()
					return dap.SocketTransport(configuration.get("host") or "localhost", configuration.get("port"))
		raise Exception("Failed to connect to Emulicious after " + maxAttempts + " attempts.\n" +
						"You can try if specifying the host to connect to, in your launch configuration.\n" +
						"If neither of the above helps, please contact the author about this error.\n" +
						"Until this is fixed, you can just start Emulicious yourself and enable Remote Debugging from Emulicious's Tools menu before trying to launch a program.")

	@property
	def configuration_snippets(self):
		snippets = self.installer.configuration_snippets()
		if not snippets:
			return

		for snippet in snippets:
			body = snippet.get("body", {})
			if body.get("program") and "command:" in snippet.get("body").get("program"):
				del body["program"]
		return snippets
