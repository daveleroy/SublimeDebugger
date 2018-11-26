from sublime_db.core.typecheck import Dict, Optional

import sublime

from .component import Component
from .layout import Layout

def _image_to_data(path: str) -> bytes:
	p = '{}/../{}'.format(sublime.packages_path(), path)
	f = open(p, 'rb')
	r = f.read()
	f.close()
	return r


def _b64_data_from_image_data(png_data: bytes):
	import base64
	return "data:image/png;base64,{}".format(base64.b64encode(png_data).decode('ascii'))

class Image:
	cached = {} #type: Dict[str, str]

	@staticmethod
	def named(name: str) -> 'Image':
		return Image(_path_for_image(name))

	def __init__(self, file: str) -> None:
		self.file = file
		if file in Image.cached:
			self.data = Image.cached[file]
		else:
			self.data = _b64_data_from_image_data(_image_to_data(file))
			Image.cached[file] = self.data

class Img (Component):
	def __init__(self, image: Image) -> None:
		super().__init__()
		self.image = image

	def html(self, layout: Layout) -> str:
		return '''<span class="img_span"><img class="{}" src="{}"></span>'''.format(self.className, self.image.data)
	

def _path_for_image(name): #type: (str) -> str
	return 'Packages/sublime_db/images/{}'.format(name)

def package_file_str(path: str) -> str:
	p = '{}/sublime_db/{}'.format(sublime.packages_path(), path)
	f = open(p, 'r')
	return f.read()

class Images:
	shared = None #type: Images
	def __init__(self) -> None:
		self.dot = Image.named('breakpoint.png')
		self.dot_emtpy = Image.named('breakpoint-broken.png')
		self.dot_expr = Image.named('breakpoint-expr.png')
		self.dot_log = Image.named('breakpoint-log.png')
		self.dot_disabled = Image.named('breakpoint-disabled.png')
		self.play = Image.named('material/baseline_play_arrow_white_48dp.png')
		self.stop = Image.named('material/baseline_stop_white_48dp.png')
		self.settings = Image.named('material/baseline_settings_white_48dp.png')
		self.thread_running = Image.named('material/baseline_360_white_48dp.png')
		self.pause = Image.named('material/baseline_pause_white_48dp.png')
		self.up = Image.named('material/baseline_keyboard_arrow_up_white_48dp.png')
		self.right = Image.named('material/baseline_keyboard_arrow_right_white_48dp.png')
		self.down = Image.named('material/baseline_keyboard_arrow_down_white_48dp.png')
		self.left = Image.named('material/baseline_keyboard_arrow_left_white_48dp.png')
		self.thread = Image.named('material/baseline_sort_white_48dp.png')
		self.dots = Image.named('material/baseline_more_horiz_white_48dp.png')
		self.not_checked = Image.named('material/baseline_check_box_outline_blank_white_48dp.png')
		self.checked = Image.named('material/baseline_check_box_white_48dp.png')
