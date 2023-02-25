# This file is written to Packages/Debugger33 when the Debugger package is loaded
import sublime_plugin

class DebuggerBridgeRequest(sublime_plugin.WindowCommand):
	def promise(self, id):
		def resolve(response) -> None:
			self.window.run_command('debugger_bridge', {
				 'id': id,
				 'resolve': response
			})

		def reject(error):
			self.window.run_command('debugger_bridge', {
				'id': id,
				'reject': str(error)
			})

		return resolve, reject


class DebuggerBridgeLspRequest(DebuggerBridgeRequest):
	def run(self, id, session_name, method, params, progress=False): #type: ignore
		resolve, reject = self.promise(id)

		try:
			from LSP.plugin import Request, LspWindowCommand
		except ImportError:
			reject('LSP does not appear to be installed')
			return


		lsp = LspWindowCommand(self.window)
		lsp.session_name = session_name

		session = lsp.session()


		if not session:
			reject('There is no active `LSP-' + session_name + '` session which is required to start debugging')
			return

		session.send_request_async(
			Request(method, params, progress=progress),
			resolve,
			reject,
		)

