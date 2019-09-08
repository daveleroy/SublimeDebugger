from ..typecheck import *
from ..commands import AutoCompleteTextInputHandler
from .. import ui

def getInputAutocomplete(label: str, on_input: Callable[[str], None], repeat: bool = False):
	label = "input debugger command"
	input = AutoCompleteTextInputHandler(label)
	def run(**args):
		on_input(args['text'])

	def run_not_main(**args):
		if repeat:
			# just re run the same command (on sublimes thread not ours to avoid flicker)
			ui.run_input_command(input, run, run_not_main=run_not_main)

	ui.run_input_command(input, run, run_not_main=run_not_main)	