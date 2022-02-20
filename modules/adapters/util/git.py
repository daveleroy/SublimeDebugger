from __future__ import annotations
from ...typecheck import *
from ...import core

import urllib.request
import urllib.error
import json
import certifi

from ...libs.semver import semver

cached_etag: dict[str, str] = {}
cached_response: dict[str, Any] = {}

# we have 60 requests per hour for an anonymous user to the github api
# conditional requests don't count against the 60 requests per hour limit so implement some very basic caching
# see https://docs.github.com/en/rest/overview/resources-in-the-rest-api
async def request_json(url: str, timeout: int|None = 30) -> Any:
	def blocking():
		headers = {
			'User-Agent': 'Sublime-Debugger',
		}
		if etag := cached_etag.get(url):
			headers['If-None-Match'] = etag

		request = urllib.request.Request(url, headers=headers)
		try:
			response = urllib.request.urlopen(request, cafile=certifi.where(), timeout=timeout)
		
		except urllib.error.HTTPError as error:
			if error.code == 304:
				return cached_response[url]
			raise error

		result = json.load(response)

		if etag := response.headers.get('Etag'):
			cached_etag[url] = etag
			cached_response[url] = result

		return result

	result = await core.run_in_executor(blocking)
	return result

async def latest_release_vsix_release(owner: str, repo: str):
	url = f'https://api.github.com/repos/{owner}/{repo}/releases'
	releases = await request_json(url)
	for release in releases:
		if release['draft'] or release['prerelease']:
			continue

		return release

	raise core.Error(f'Unable to find a suitable release in {owner} {repo}')


async def latest_release_vsix(owner: str, repo: str) -> str:
	release = await latest_release_vsix_release(owner, repo)
	for asset in release.get('assets', []):
		if asset['name'].endswith('.vsix'):
			return asset['browser_download_url']

	raise core.Error(f'Unable to find a suitable asset in latest release of {owner} {repo}')


def removeprefix(text: str, prefix: str):
	return text[text.startswith(prefix) and len(prefix):]

async def installed_status(owner: str, repo: str, version: str|None, log: core.Logger = core.stdio):
	if not version:
		return None

	
	log.info(f'github {owner} {repo} checking for updates')

	release = await latest_release_vsix_release(owner, repo)
	tag: str = removeprefix(release['tag_name'], 'v')

	if semver.compare(tag, removeprefix(version, 'v')) != 0:
		log.info(f'github {owner} {repo} done "Update Available {tag}"')
		return f'Update Available {tag}'

	log.info(f'github {owner} {repo} done')
	return None
