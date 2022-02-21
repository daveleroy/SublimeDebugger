from __future__ import annotations
from .typecheck import*
from .import dap
from .import core

import sublime
import json
import os


def save_schema(adapters: list[dap.AdapterConfiguration]):

	allOf: list[Any] = []
	installed_adapters: list[str] = []
	for adapter in adapters:
		if adapter.installed_version:
			installed_adapters.append(adapter.type)

	definitions = {}
	debugger_snippets = []

	for adapter in adapters:
		schema = adapter.configuration_schema or {}
		snippets = adapter.configuration_snippets or []

		requests: list[str] = []
		for key, value in schema.items():
			requests.append(key)

		definitions[adapter.type] = {
			'properties': {
				'request': {
					'type': 'string',
					'description': F'Request type of configuration.',
					'enum': requests,
				},
				'name': {
					'type': 'string',
					'description': 'Name of configuration; appears in the launch configuration drop down menu.',
				},
				'pre_debug_task': {
					'type': 'string',
					'description': 'Name of task to run before debugging starts',
				},
				'post_debug_task': {
					'type': 'string',
					'description': 'name of task to run after debugging ends',
				}
			}
		}

		allOf.append({
			'if': {
				'properties': {'type': { 'const': adapter.type }},
			},
			'then': {
				'$ref': F'#/definitions/{adapter.type}'
			},
		})

		for key, value in schema.items():
			# make sure all the default properties are defined here because we are setting additionalProperties to false
			value['additionalProperties'] = False
			value.setdefault('properties', {})
			value.setdefault('type', 'object')
			value['properties']['name'] = { 'type':'string' }
			value['properties']['type'] = { 'type':'string' }
			value['properties']['request'] = { 'type':'string' }
			value['properties']['pre_debug_task'] = { 'type':'string' }
			value['properties']['post_debug_task'] = { 'type':'string' }
			
			definitions[f'{adapter.type}_{key}'] = value
			
			allOf.append({
				'if': {
					'properties': {'type': { 'const': adapter.type }, 'request': { 'const': key }},
				},
				'then': {
					'$ref': F'#/definitions/{adapter.type}_{key}'
				},
			})
		
		for snippet in snippets:
			debugger_snippets.append({
				'label': snippet['label'],
				'body': snippet['body'],
				# 'bodyText': core.json_encode_json_language_service_format(snippet['body']),
				'description': snippet.get('description')
			})

	debugger_configurations = {
		'type': 'object',
		'properties': {
			'type': {
				'type':'string',
				'description': 'Type of configuration.',
				'enum': installed_adapters,
			},
		},
		 'defaultSnippets': debugger_snippets,
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
		'type': 'object',
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

	schema_debug_configurations = {
		'contributions': {
			'settings':[{
				'file_patterns': ['/*.sublime-project'],
				'schema': {
					'definitions': definitions,
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
		file.write(json.dumps(schema_debug_configurations, indent='  '))