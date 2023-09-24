from __future__ import annotations
from typing import Any

from ..settings import SettingsRegistery
from .adapter import AdapterConfiguration
from ..import core

import json


def generate_lsp_json_schema():
	adapters = AdapterConfiguration.registered

	allOf: list[Any] = []
	installed_adapters: list[str] = []
	all_adapters: list[str] = []
	for adapter in adapters:
		for type in adapter.types:
			all_adapters.append(type)
			if adapter.installed_version:
				installed_adapters.append(type)

	definitions = {}
	debugger_snippets = []

	definitions['type'] = {
		'properties': {
				'type': {
				'type':'string',
				'description': 'Type of configuration.',
				'enum': all_adapters,
			},
		},
		'required': ['type'],
	}

	definitions['type_installed'] = {
		'properties': {
				'type': {
				'type':'string',
				'description': 'Type of configuration.',
				'enum': installed_adapters,
				'errorMessage': 'This adapter is not installed, install this adapter to get completions',
			},
		},
		'required': ['type'],
	}

	allOf.append({
		'if': {
			'$ref': F'sublime://settings/debugger#/definitions/type',
		},
		'then': {
			'$ref': F'sublime://settings/debugger#/definitions/type_installed'
		},
		'else': {
			'$ref': F'sublime://settings/debugger#/definitions/type',
		},
	})

	for adapter in adapters:
		schema = adapter.configuration_schema or {}
		snippets = adapter.configuration_snippets or []
		installed = adapter.installed_version

		types = adapter.types
		key = adapter.types[0]

		if not installed:
			continue

		if installed and not schema:
			core.info(f'Warning: {adapter.type}: schema not provided')

		if installed and not snippets:
			core.info(f'Warning: {adapter.type}: snippets not provided')

		requests: list[str] = []
		for request, value in schema.items():
			requests.append(request)

		definitions[key] = {
			'properties': {
				'request': {
					'type': 'string',
					'description': F'Request type of configuration.',
					'enum': requests,
				},
				'name': {
					'type': 'string',
					'description': 'Name of configuration which appears in the launch configuration drop down menu.',
				},
			},
			'required': ['type', 'name', 'request'],
		}

		for type in types:
			allOf.append({
				'if': {
					'properties': { 'type': { 'const': type }, },
					'required': ['type'],
				},
				'then': {
					'$ref': F'sublime://settings/debugger#/definitions/{key}'
				},
			})

		for request, value in schema.items():
			# make sure all the default properties are defined here because we are setting additionalProperties to false
			value.setdefault('properties', {})
			value.setdefault('type', 'object')

			value['properties']['pre_debug_task'] = {
				'type': 'string',
				'description': 'Name of task to run before debugging starts',
			}
			value['properties']['post_debug_task'] = {
				'type': 'string',
				'description': 'name of task to run after debugging ends',
			}
			value['properties']['osx'] = {
				'$ref': F'sublime://settings/debugger#/definitions/{key}.{request}',
				'description': 'MacOS specific configuration attributes',
			}
			value['properties']['windows'] = {
				'$ref': F'sublime://settings/debugger#/definitions/{key}.{request}',
				'description': 'Windows specific configuration attributes',
			}
			value['properties']['linux'] = {
				'$ref': F'sublime://settings/debugger#/definitions/{key}.{request}',
				'description': 'Linux specific configuration attributes',
			}

			definitions[f'{key}.{request}'] = value

			for type in types:
				allOf.append({
					'if': {
						'properties': {'type': { 'const': type }, 'request': { 'const': request }},
						'required': ['name', 'type', 'request']
					},
					'then': {
						'unevaluatedProperties': False,
						'allOf': [
							{ '$ref': F'sublime://settings/debugger#/definitions/type' },
							{ '$ref': F'sublime://settings/debugger#/definitions/{key}' },
							{ '$ref': F'sublime://settings/debugger#/definitions/{key}.{request}'},
						]
					},
				})

		for snippet in snippets:
			debugger_snippets.append(snippet)

	definitions['debugger_configuration'] = {
		'defaultSnippets': debugger_snippets,
		'allOf': allOf,
	}

	definitions['debugger_compound'] = {
		'properties': {
			'name': {
				'type': 'string',
				'description': 'Name of compound which appears in the launch configuration drop down menu.',
			},
			'configurations': {
				'type': 'array',
				'description': 'Names of configurations that compose this compound configuration',
				'items': { 'type': 'string' }
			}
		},
		'required': ['name', 'configurations']
	}

	definitions['debugger_task'] = {
		'allOf': [
			{ '$ref': 'sublime://schemas/sublime-build' },
			{
				'properties': {
					'name': {
						'type': 'string',
						'description': 'Name of task',
					}
				},
				'required': ['name']
			}
		]
	}

	definitions_schma = {
		'schema': {
			'$id': 'sublime://settings/debugger',
			'definitions': definitions,
		}
	}

	schema_debug_configurations = {
		'contributions': {
			'settings': [
				definitions_schma,
				{
					'file_patterns': ['/*.sublime-project'],
					'schema': {
						'properties': {
							'debugger_configurations': {
								'description': 'Debugger Configurations',
								'type': 'array',
								'items': { '$ref': F'sublime://settings/debugger#/definitions/debugger_configuration' },
							},
							'debugger_tasks': {
								'description': 'Debugger Tasks',
								'type': 'array',
								'items': { '$ref': F'sublime://settings/debugger#/definitions/debugger_task' },
							},
							'debugger_compounds': {
								'description': 'Debugger Compounds',
								'type': 'array',
								'items': { '$ref': F'sublime://settings/debugger#/definitions/debugger_compound' },
							}
						},
					},
				},
				{
					'file_patterns': ['Debugger.sublime-settings'],
					'schema': SettingsRegistery.schema(),
				}
			]
		}
	}

	with open(core.package_path('sublime-package.json'), 'w') as file:
		file.write(json.dumps(schema_debug_configurations, indent='  '))
