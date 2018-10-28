import sublime
import sys
import os

# import all the commands so that sublime sees them
from sublime_db.main.commands import *
from sublime_db.ui import ViewEventsListener
from sublime_db.main import main

def plugin_loaded():
	# um use vscode or a seperate instance of sublime for debugging this plugin or you will lockup when you hit a breakpoint...
	# import ptvsd
	#try:		
	#	ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)
	#except:
	#	pass
	
	print('plugin_loaded')
	main.startup()
	
def plugin_unloaded():
	print('plugin_unloaded')
	main.shutdown()