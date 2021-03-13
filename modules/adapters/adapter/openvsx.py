from __future__ import annotations
from .git import request_json, removeprefix
from ...libs.semver import semver

async def latest_release_vsix(owner: str, repo: str):
	response = await request_json(f'https://open-vsx.org/api/{owner}/{repo}/latest')
	return response['files']['download']

async def installed_status(owner: str, repo: str, version: str|None):
	if not version:
		return None

	response = await request_json(f'https://open-vsx.org/api/{owner}/{repo}/latest')
	tag = removeprefix(response['version'], 'v')

	if semver.compare(tag, removeprefix(version, 'v')) != 0:
		return f'Update Available {tag}'

	return None