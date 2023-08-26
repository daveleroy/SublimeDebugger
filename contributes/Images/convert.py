import os
import subprocess
import sys
import tempfile

files = [
	'step_over.png',
	'stop.png',
	'continue.png',
	'thread_running.png',
	'settings.png',
	'up.png',
	'clear.png',
	'step_into.png',
	'thread_stopped.png',
	'pause.png',
	'thread.png',
	'open.png',
	'check_mark.png',
	'step_out.png',
	'play.png',
	'loading.png',
	'close.png',
]

files_universal = [
	'breakpoint-broken.png',
	'breakpoint-disabled.png',
	'breakpoint-expr.png',
	'breakpoint-log.png',
	'breakpoint.png',
]

cache_directory_t = tempfile.TemporaryDirectory()
cache_directory = cache_directory_t.name

def mkdir(path: str):
	try: os.mkdir(path)
	except: ...

def cmd(command: str):
	cmd = subprocess.run(command, capture_output=True, shell=True)
	if cmd.stdout: print(cmd.stdout)
	if cmd.stderr: print(cmd.stderr, file=sys.stderr)

mkdir('dark')
mkdir('light')
mkdir('universal')

for file in files_universal:
	print(file)
	cmd(f'magick "base/{file}" -resize 48x48 png32:universal/unoptimized-{file}')
	cmd(f'magick "base/{file}" -resize 48x48 universal/{file}')
	cmd(f'pngquant "universal/{file}" --ext ".png" --speed 1 -f --quality 1')

for file in files:
	print(file)

	filename= file
	filename_no_ext= file.removesuffix(".png")

	file_negated_temp=f'{cache_directory}/{filename_no_ext}_negated.png'
	file_blur_temp=f'{cache_directory}/{filename_no_ext}_blur.png'

	cmd(f'magick convert -alpha set -background none -channel A -evaluate multiply 0.1 +channel -resize 128x128 -blur 32x32 "base/{filename}" "{file_blur_temp}"')
	cmd(f'magick convert -channel RGB -negate "base/{filename}" "{file_negated_temp}"')
	

	for ext, size in [["", "48x48"]]:
		filename_no_ext_size=f"{filename_no_ext}{ext}.png"
		
		# generate dark/light image + blurred (always dark) background
		file_dark = f'dark/{filename_no_ext}{ext}.png'
		file_light = f'light/{filename_no_ext}{ext}.png'

		file_disabled_dark = f'dark/{filename_no_ext}_disabled{ext}.png'
		file_disabled_light = f'light/{filename_no_ext}_disabled{ext}.png'


		# generate dark/light image + blurred (always dark) background
		cmd(f'magick convert -resize {size} "{file_blur_temp}" "base/{filename}" -composite "{file_dark}"')
		cmd(f'magick convert -resize {size} "{file_blur_temp}" "{file_negated_temp}" -composite "{file_light}"')

		# generate dark/lighht disabled variants
		cmd(f'magick convert -alpha set -background none -channel A -evaluate multiply 0.15 +channel -resize {size} "{file_blur_temp}" "base/{filename}" -composite "{file_disabled_dark}"')
		cmd(f'magick convert -alpha set -background none -channel A -evaluate multiply 0.15 +channel -resize {size} "{file_blur_temp}" "{file_negated_temp}" -composite "{file_disabled_light}"')


		for f in [file_dark, file_light, file_disabled_dark, file_disabled_light]:
			cmd(f'pngquant "{f}" --ext ".png" --speed 1 -f --quality 25')
