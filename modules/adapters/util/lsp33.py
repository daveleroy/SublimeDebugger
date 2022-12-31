# This file is written to Packages/Debugger33 when the Debugger package is loaded
from LSP.plugin import Request, LspWindowCommand

class DebuggerLspBridgeRequest(LspWindowCommand):
    def is_enabled(self) -> bool:
        return True

    def run(self, id, session_name, method, params, progress=False):
        self.session_name = session_name
        session = self.session()

        def _on_request_success(response) -> None:
            self.window.run_command('debugger_lsp_bridge_response', {
                 'id': id,
                 'resolve': response
            })

        def _on_request_error(error):
            self.window.run_command('debugger_lsp_bridge_response', {
                'id': id,
                'reject': str(error)
            })

        if not session:
            _on_request_error('There is no active `LSP-' + session_name + '` session which is required to start debugging')
            return

        session.send_request_async(
            Request(method, params, progress=progress),
            _on_request_success,
            _on_request_error,
        )
