from ...typecheck import *
from ...import core
from ...import ui

from .install import VSCodeAdapterInstall, AdapterInstall

import sublime

def _expand_variables_and_platform(json: dict, variables: Optional[dict]) -> dict:
	platform = None #type: Optional[dict]
	if core.platform.osx:
		platform = json.get('osx')
	elif core.platform.linux:
		platform = json.get('linux')
	elif core.platform.windows:
		platform = json.get('windows')

	if platform:
		json = json.copy()
		for key, value in platform.items():
			json[key] = value
	
	if variables is not None:
		return sublime.expand_variables(json, variables)

	return json

class Adapter:
	def __init__(self, type: str, json: dict, variables: dict) -> None:
		json = _expand_variables_and_platform(json, None)
		install_json = json.get('install')

		variables = variables.copy()

		self.installer = None
		if install_json:
			if install_json["type"] == "vscode":
				self.installer = VSCodeAdapterInstall.from_json(_expand_variables_and_platform(install_json, variables))
				variables["install_path"] = self.installer.path
			else:
				raise core.Error("unhandled adapter install type")

		json = _expand_variables_and_platform(json, variables)
		self.command = json['command']		
		self.type = type
		self.hover_word_seperators = json.get('hover_word_seperators')
		self.hover_word_regex_match = json.get('hover_word_regex_match')
		self.snippets = [] #type: List[dict]
		self.load_installation_if_needed()

	@property
	def installed(self) -> bool:
		if self.installer:
			return self.installer.installed
		return True

	def load_installation_if_needed(self) -> None:
		if not self.installer:
			return
		self.snippets = self.installer.snippets()

	@core.coroutine
	def install(self, log: core.Logger) -> core.awaitable[None]:
		yield from self.installer.install(log)
		self.load_installation_if_needed()

def install_adapters_menu(adapters: Sequence[Adapter], log: core.Logger):
	items = []
	for adapter in adapters:
		if not adapter.installer:
			continue

		def install(adapter):
			installer = adapter.installer
			assert installer

			def install():
				log.info("Installing Adapter: {}".format(installer.name))
				try:
					yield from adapter.install(log)
				except core.Error as e:
					log.error("Failed Installing Adapter: {}".format(e))
			
			core.run(install())

		items.append(
			ui.InputListItemChecked(
				lambda adapter=adapter: install(adapter), 
				adapter.installer.name, 
				adapter.installer.name, 
				adapter.installed
			)
		)

	return ui.InputList(items, "Install Debug Adapters")
