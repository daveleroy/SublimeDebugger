import sublime
import sys
import os

# import all the commands so that sublime sees them
from debug.main.commands import *
from debug.ui import ViewEventsListener
 
from debug.main.main import startup, shutdown

def plugin_loaded():
	# um use vscode or a seperate instance of sublime for debugging this plugin or you will lockup when you hit a breakpoint...
	# import ptvsd
	#try:		
	#	ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)
	#except:
	#	pass

	print('plugin_loaded')
	startup()
	

def plugin_unloaded():
	print('plugin_unloaded')
	shutdown()
	
	
		
