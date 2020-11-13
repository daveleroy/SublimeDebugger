import sublime
from ...import core
from ...typecheck import*

from .adapters import AdapterConfiguration
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

	debugger_configurations = {
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
			},
			'pre_debug_task': {
				'type': 'string',
				'description': 'Name of task to run before debugging starts',
			},
			'post_debug_task': {
				'type': 'string',
				'description': 'name of task to run after debugging ends',
			}
		},
		'required': ['type', 'name', 'request'],
		'allOf': allOf,
	}

	debugger_tasks = {
		'allOf': [
			{ '$ref': 'sublime://schemas/sublime-build' },
			{
				'properties': {
					'name': {
						'type': 'string'
					}
				},
				'required': ['name']
			}
		]
	}

	debugger_compounds = {
		'allOf': [
			{
				'properties': {
					'name': {
						'type': 'string'
					},
					'configurations': {
						'type': 'array',
						'items': { 'type': 'string' }
					}
				},
				'required': ['name', 'configurations']
			}
		]
	}

	schema_debug_configurations = {
		'contributions': {
			'settings':[{
				'file_patterns': ['/*.sublime-project'],
				'schema': {
					'properties': {
						'debugger_configurations': {
							'description': 'Debugger Configurations',
							'type': 'array',
							'items': debugger_configurations,
						},
						'debugger_tasks': {
							'description': 'Debugger Tasks',
							'type': 'array',
							'items': debugger_tasks
						},
						'debugger_compounds': {
							'description': 'Debugger Compounds',
							'type': 'array',
							'items': debugger_compounds
						}
					},
				},
			}]
		}
	}

	path = os.path.join(core.current_package(), 'sublime-package.json')
	with open(path, 'w') as file:
		file.write(sublime.encode_value(schema_debug_configurations, True))