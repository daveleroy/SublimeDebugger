from __future__ import annotations
from .git import request_json, removeprefix
from ...libs.semver import semver
from ...import core

async def latest_release_vsix(owner: str, repo: str) -> str:
	response = await request_json(f'https://open-vsx.org/api/{owner}/{repo}/latest')
	return response['files']['download']

async def installed_status(owner: str, repo: str, version: str|None, log: core.Logger = core.stdio):
	if not version:
		return None

	log.info(f'openvsx {owner}/{repo}')

	try:
		response = await request_json(f'https://open-vsx.org/api/{owner}/{repo}/latest')
	except Exception as e:
		log.log('error', f'openvsx {owner}/{repo}: {e}')
		raise e

	tag = removeprefix(response['version'], 'v')
	version = removeprefix(version, 'v')
	
	if semver.compare(tag, version) != 0:
		# log.info(f'openvsx {owner} {repo} done "Update Available {tag}"')
		log.log('warn', f'openvsx {owner} {repo}: Update Available {version} -> {tag}')

		return f'Update Available {tag}'

	# log.info(f'openvsx {owner} {repo} done')
	return None