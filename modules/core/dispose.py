from ..typecheck import *
from .log import log_exception

class Disposables:
	def __init__(self):
		self.disposables = {} #type: Dict[int, Any]

	def __iadd__(self, disposable) -> Any:
		try:
			disposable.dispose
		except AttributeError:
			log_exception("expected dispose() function")
		
		self.disposables[id(disposable)] = disposable
		return self

	def __isub__(self, disposable) -> Any:
		self.disposables[id(disposable)].dispose()
		return self

	def dispose(self):
		for value in self.disposables.values():
			value.dispose()
		self.disposables.clear()


class disposables:
	def __init__(self):
		self.disposables = Disposables()

	def dispose(self):
		self.disposables.dispose()