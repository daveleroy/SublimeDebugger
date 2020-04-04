from ... typecheck import *
from ... import ui
from ..watch import Watch, WatchView
from ..variables import VariableComponent
from ..debugger_sessions import DebuggerSessions

import sublime


class VariablesView (ui.div):
	def __init__(self, sessions: DebuggerSessions) -> None:
		super().__init__()
		self.sessions = sessions
		self.sessions.on_updated_variables.add(lambda session: self.on_updated(session))
		self.sessions.on_removed_session.add(lambda session: self.on_updated(session))

	def on_updated(self, session):
		self.dirty()

	def render(self) -> ui.div.Children:
		session = self.sessions.selected_session
		if not session:
			return

		variables = [VariableComponent(variable) for variable in session.variables]
		if variables:
			variables[0].set_expanded()

		return variables


class VariablesPanel (ui.div):
	def __init__(self, sessions: DebuggerSessions) -> None:
		super().__init__()
		self.watch_view = WatchView(sessions.watch)
		self.variables_view = VariablesView(sessions)

	def render(self) -> ui.div.Children:
		return [
			self.watch_view,
			self.variables_view,
		]
