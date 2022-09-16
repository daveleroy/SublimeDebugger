from __future__ import annotations
import re 
from .typecheck import *

def ansi_colorize(text, color, previous_color):
	text = text.replace('\r\n', '\n')

	def replacement(x: Any):
		try:
			return escape_codes_by_code[x.group()]['match']
		except KeyError:
			return ''

	text = ansi_escape.sub(replacement, text)
	
	if color != previous_color:
		return escape_code(color) + text
	else:
		return text

def escape_code(color: str):
	match = escape_codes_by_color.get(color)
	if not match:
		return '\u200c'

	return f'\u200c{match["match"]}'


# from https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')

escape_codes: list[dict[str, Any]] = [
	{
		'color': 'foreground',
		'escape': ['\u001b[30m', '\u001b[37m', '\u001b[39m', '\u001b[0m', '\u001b[90m'],
		'match': '\u200c',
	},
	{
		'color': 'red',
		'escape': ['\u001b[31m', '\u001b[91m'],
		'scope': 'region.redish.debugger debugger.background',
		'match': '\u200b',
	},
	{
		'color': 'green',
		'escape': ['\u001b[32m', '\u001b[92m'],
		'scope': 'region.greenish.debugger debugger.background',
		'match': '\u200b\u200b',
	},
	{
		'color': 'yellow',
		'escape': ['\u001b[33m', '\u001b[93m'],
		'scope': 'region.yellowish.debugger debugger.background',
		'match': '\u200b\u200b\u200b',
	},
	{
		'color': 'blue',
		'escape': ['\u001b[34m', '\u001b[94m'],
		'scope': 'region.bluish.debugger debugger.background',
		'match': '\u200b\u200b\u200b\u200b',
	},
	{
		'color': 'magenta',
		'escape': ['\u001b[35m', '\u001b[95m'],
		'scope': 'region.purplish.debugger debugger.background',
		'match': '\u200b\u200b\u200b\u200b\u200b',
	},
	{
		'color': 'cyan',
		'escape': ['\u001b[36m', '\u001b[96m'],
		'scope': 'region.cyanish.debugger debugger.background',
		'match': '\u200b\u200b\u200b\u200b\u200b\u200b',
	},
	{
		'color': 'comment',
		'escape': [],
		'scope': 'comment.debugger',
		'match': '\u200b\u200b\u200b\u200b\u200b\u200b\u200b',
	},
]

escape_codes_by_code: dict[str|None, Any] = {}
escape_codes_by_color: dict[str|None, Any] = {}

for item in escape_codes:
	escape_codes_by_color[item['color']] = item

	for escape in item['escape']:
		escape_codes_by_code[escape] = item

def generate_ansi_syntax():
	yaml = '''%YAML 1.2
---
hidden: true
scope: debugger.console
name: Debugger Console

contexts:
	main:
'''
	for item in reversed(escape_codes):
		scope = item.get('scope')
		if not scope:
			continue

		yaml += f'''		- match: '{item['match']}'
			scope: {scope}
			push:
				- meta_scope: {scope}
				- match: '\u200c'
					scope: {scope}
					pop: true
'''
	return yaml.replace('\t', '  ')