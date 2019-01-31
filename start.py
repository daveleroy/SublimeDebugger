import threading
from sublime_db.core.typecheck import Set

import sublime

from sublime_db import ui
from sublime_db import core

# import all the commands so that sublime sees them
from sublime_db.main.commands import *
from sublime_db.main.main import *
from sublime_db.ui import ViewEventsListener
from sublime_db.main.util import get_setting
from sublime_db.main.output_panel import *


@core.async
def startup_main_thread() -> None:
	print('Starting up')
	ui.startup()
	ui.import_css('{}/{}'.format(sublime.packages_path(), 'sublime_db/main/components/components.css'))

	was_opened_at_startup = set() #type: Set[int]

	def on_view_activated(view: sublime.View) -> None:
		# there is probabaly a better way to filter out things like output panels and stuff
		if not view.file_name():
			return
		window = view.window()
		if window and (not window.id() in was_opened_at_startup) and get_setting(view, 'open_at_startup', False):
			was_opened_at_startup.add(window.id())
			Main.forWindow(window, True)

	ui.view_activated.add(on_view_activated)


def startup() -> None:
	core.startup()
	core.run(startup_main_thread())


@core.async
def shutdown_main_thread(event: threading.Event) -> None:
	# we just want to ensure that we still set the event if we had an exception somewhere
	# otherwise shutdown could lock us up
	try:
		print('shutdown')
		for key, instance in dict(Main.instances).items():
			instance.dispose()
		Main.instances = {}
		ui.shutdown()
	except Exception as e:
		raise e
	finally:
		event.set()


def shutdown() -> None:
	event = threading.Event()
	core.run(shutdown_main_thread(event))
	event.wait()
	core.shutdown()


def plugin_loaded():
	# um use vscode or a seperate instance of sublime for debugging this plugin or you will lockup when you hit a breakpoint...
	# import ptvsd
	# try:
	#	ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)
	# except:
	#	pass

	print('plugin_loaded')
	startup()


def plugin_unloaded():
	print('plugin_unloaded')
	shutdown()
