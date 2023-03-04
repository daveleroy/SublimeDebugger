from __future__ import annotations
from dataclasses import dataclass
from typing import Any, BinaryIO

from urllib.request import Request, urlopen
from urllib.error import HTTPError
from gzip import GzipFile

import sublime

from ...core.json import JSON, json_decode_b

from ... import core

@dataclass
class Response:
	headers: dict[str, str]
	data: BinaryIO

	def __init__(self, response: Any) -> None:
		content_encoding = response.headers.get('Content-Encoding')
		if content_encoding == 'gzip':
			data_file: BinaryIO = GzipFile(fileobj=response) #type: ignore
		elif content_encoding == 'deflate':
			data_file: BinaryIO = response
		elif content_encoding:
			raise core.Error(f'Unknown Content-Encoding {content_encoding}')
		else:
			data_file = response

		self.headers = response.headers
		self.data= data_file

_cached_etag: dict[str, str] = {}
_cached_response: dict[str, JSON] = {}

# we have 60 requests per hour for an anonymous user to the github api
# conditional requests don't count against the 60 requests per hour limit so implement some very basic caching
# see https://docs.github.com/en/rest/overview/resources-in-the-rest-api
@core.run_in_executor
def request(url: str, timeout: int|None = 30):
	headers = {
		'User-Agent': 'Sublime-Debugger',
		'Accept-Encoding': 'gzip, deflate'
	}

	try:
		return Response(urlopen(Request(url, headers=headers), timeout=timeout))
	except Exception as error:
		raise core.Error(f'{error}: Unable to download file ${url}')


@core.run_in_executor
def json(url: str, timeout: int|None = 30) -> JSON:
	try:
		headers = {
			'User-Agent': 'Sublime-Debugger',
			'Accept-Encoding': 'gzip, deflate'
		}
		if etag := _cached_etag.get(url):
			headers['If-None-Match'] = etag

		try:
			response = Response(urlopen(Request(url, headers=headers), timeout=timeout))

		except HTTPError as error:
			if error.code == 304 and _cached_response[url]:
				return _cached_response[url]
			raise error

		result = json_decode_b(response.data)
		if etag := response.headers.get('Etag'):
			_cached_etag[url] = etag
			_cached_response[url] = result

		return result

	except Exception as error:
		raise core.Error(f'{error}: Unable to download file ${url}')


async def download_and_extract_zip(url: str, path: str, log: core.Logger):
	def log_info(value: str):
		sublime.status_message(f'Debugger: {value}')
		# core.call_soon_threadsafe(log.info, value)

	archive_name = f'{path}.zip'
	response = await request(url)

	@core.run_in_executor
	def blocking():

		with open(archive_name, 'wb') as out_file:
			_copyfileobj(response.data, out_file, log_info, int(response.headers.get('Content-Length', '0')))

		log_info('...downloaded')
		log_info('extracting...')
		with core.ZipFile(archive_name) as zf:
			top = {item.split('/')[0] for item in zf.namelist()}
			zipinfos = zf.infolist()



			# if the zip is a single item extract rename it so its not multiple levels deep
			if len(top) == 1:
				folder = top.pop()
				for zipinfo in zipinfos:
					zipinfo.filename = zipinfo.filename.lstrip(folder)
					zf.extract(zipinfo, path)
			else:
				zf.extractall(path)

		log_info('...extracted')


	log.info('Downloading {}'.format(url))

	await blocking()
	core.remove_file_or_dir(archive_name)


# https://stackoverflow.com/questions/29967487/get-progress-back-from-shutil-file-copy-thread
def _copyfileobj(fsrc, fdst, log_info, total, length=128*1024):
	copied = 0

	while True:
		buf = fsrc.read(length)
		if not buf:
			break
		fdst.write(buf)
		copied += len(buf)

		# handle the case where the total size isn't known
		if total:
			log_info('{:.2f} mb {}%'.format(copied/1024/1024, int(copied/total*100)))
		else:
			log_info('{:.2f} mb'.format(copied/1024/1024))
