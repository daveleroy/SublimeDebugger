from ...import core
from ...typecheck import*

from .adapter import Adapter
import json
import os

def save_schema(adapters: List[Adapter]):

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

	schema = {
		'description': 'Debugger Configuration File',
		'type': 'object',
		'properties': {
			'configurations': {
				'type': 'array',
				'items': debuggers_schema,
			}
		},
		'required': ['configurations']
	}
	

	path = os.path.join(core.current_package(), 'data', 'schema.json')
	with open(path, 'w') as file:
		file.write(json.dumps(schema, indent="\t"))