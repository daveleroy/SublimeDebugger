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

async def latest_release_with_vsix_asset(owner: str, repo: str):
	url = f'https://api.github.com/repos/{owner}/{repo}/releases'
	releases = await request_json(url)
	for release in releases:
		if release['draft'] or release['prerelease']:
			continue

		for asset in release.get('assets', []):
			if asset['name'].endswith('.vsix'):
				url: str = asset['browser_download_url']
				return (release, url)

	raise core.Error(f'Unable to find a suitable release in {owner} {repo}')


async def latest_release_vsix(owner: str, repo: str) -> str:
	_, url = await latest_release_with_vsix_asset(owner, repo)
	return url

def removeprefix(text: str, prefix: str):
	return text[text.startswith(prefix) and len(prefix):]

async def installed_status(owner: str, repo: str, version: str|None, log: core.Logger = core.stdio):
	if not version:
		return None

	log.info(f'github {owner}/{repo}')

	try:
		release, _ = await latest_release_with_vsix_asset(owner, repo)
	except Exception as e:
		log.log('error', f'github {owner}/{repo}: {e}')
		raise e
	
	tag = removeprefix(release['tag_name'], 'v')
	version = removeprefix(version, 'v')

	if semver.compare(tag, version) != 0:
		log.log('warn', f'github {owner}/{repo}: Update Available {version} -> {tag}')
		return f'Update Available {tag}'

	# log.info(f'github {owner} {repo} done')
	return None
