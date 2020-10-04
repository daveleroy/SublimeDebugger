import sublime
from ...import core
from ...typecheck import*

from .adapter import AdapterConfiguration
import json
import os

def save_schema(adapters: List[AdapterConfiguration]):

	allOf = []
	for adapter in adapters:
		if not adapter.configuration_schema:
			continue

		for key, value in adapter.configuration_schema.items():
			allOf.append({
				'if': {
					'properties': {'type': { 'const': adapter.type }, 'request': { 'const': key }},
				},
				'then': value,
			})

	debuggers_schema = {
		'type': 'object',
		'properties': {
			'name': {
				'description': 'Name of configuration; appears in the launch configuration drop down menu.',
				'type':'string'
			},
			'type': {
				'type':'string',
				'description': 'Type of configuration.'
			},
			'request': {
				'type': 'string',
				'description': 'Request type of configuration. Can be "launch" or "attach".',
				'enum': [ 'attach', 'launch' ]
			}
		},
		'required': ['type', 'name', 'request'],
		'allOf': allOf,
	}

	schema_debug_configurations = {
		'contributions': {
			'settings':[{
				'file_patterns': ['/*.sublime-project'],
				'schema': {
					'properties': {
						'debugger_configurations': {
							'description': 'Debug configurations',
							'type': 'array',
							'items': debuggers_schema,
						}
					},
				},
			}]
		}
	}

	path = os.path.join(core.current_package(), 'sublime-package.json')
	with open(path, 'w') as file:
		file.write(sublime.encode_value(schema_debug_configurations, True))