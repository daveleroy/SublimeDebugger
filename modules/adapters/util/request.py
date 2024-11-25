from __future__ import annotations
from dataclasses import dataclass
from typing import Any, BinaryIO

from urllib.request import Request, urlopen
from urllib.error import HTTPError
from gzip import GzipFile
import tarfile

import sublime

from ...core.json import JSON, json_decode

from ... import core

@dataclass
class URLRequest:
	headers: dict[str, str]
	data: BinaryIO

	def __init__(self, url: str, timeout: int|None = 30, headers: dict[str, str] = {}) -> None:
		actual_headers = {
			'user-agent': 'Sublime-Debugger',
			'accept-encoding': 'gzip, deflate'
		}

		for header in headers:
			actual_headers[header.lower()] = headers[header]

		response = urlopen(Request(url, headers=actual_headers), timeout=timeout)

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
_cached_response: dict[str, bytes] = {}


@core.run_in_executor
def request(url: str, timeout: int|None = 30, headers: dict[str, str] = {}):
	try:
		return URLRequest(url, timeout, headers)
	except Exception as error:
		raise handle_request_error(url, error)


@core.run_in_executor
def json(url: str, headers: dict[str, str] = {}) -> JSON:
	return json_decode(request_bytes(url, headers=headers))

@core.run_in_executor
def text(url: str, headers: dict[str, str] = {}) -> str:
	return request_bytes(url, headers=headers).decode('utf-8')

# we have 60 requests per hour for an anonymous user to the github api
# conditional requests don't count against the 60 requests per hour limit so implement some very basic caching
# see https://docs.github.com/en/rest/overview/resources-in-the-rest-api

def request_bytes(url: str, timeout: int|None = 30, headers: dict[str, str] = {}) -> bytes:
	try:
		if etag := _cached_etag.get(url):
			headers['If-None-Match'] = etag

		try:
			response = URLRequest(url, headers=headers, timeout=timeout)

		except HTTPError as error:
			if error.code == 304 and _cached_response[url]:
				return _cached_response[url]
			raise error

		result = response.data.read()
		if etag := response.headers.get('Etag'):
			_cached_etag[url] = etag
			_cached_response[url] = result

		return result

	except Exception as error:
		raise handle_request_error(url, error)

def handle_request_error(url: str, error: Exception):
	if isinstance(error, HTTPError):
		return core.Error(f'Unable to perform request ({error.code}) ({url})')
	else:
		return core.Error(f'Unable to perform request ({error}) ({url})')

async def download_and_extract_zip(url: str, path: str, extract_folder: str|None = None, *, log: core.Logger = core.stdio):
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

			if extract_folder:
				for zipinfo in zipinfos:
					if zipinfo.filename.startswith(extract_folder):
						zipinfo.filename= zipinfo.filename.lstrip(extract_folder)
						zf.extract(zipinfo, path)

			# if the zip is a single item extract rename it so its not multiple levels deep
			elif len(top) == 1:
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

async def download_and_extract_targz(url: str, path: str, extract_folder: str|None = None, *, log: core.Logger = core.stdio):
	def log_info(value: str):
		sublime.status_message(f'Debugger: {value}')
		# core.call_soon_threadsafe(log.info, value)

	archive_name = f'{path}.tar.gz'
	response = await request(url)

	@core.run_in_executor
	def blocking():

		with open(archive_name, 'wb') as out_file:
			_copyfileobj(response.data, out_file, log_info, int(response.headers.get('Content-Length', '0')))

		log_info('...downloaded')
		log_info('extracting...')
		with tarfile.open(archive_name, 'r:gz') as tz:
			tz.extractall(path)

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
