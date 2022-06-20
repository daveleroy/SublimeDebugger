import time
import sys

from threading import Thread
from typing import List

def some_random_variables():
	integer = 1
	floating = 2.345
	string = "abc"
	array = [integer, floating, string]
	table = {
		'string': string,
		'intger': integer,
		'float': floating,
		'array': array,
	}

	print(string, flush=True)
	print(integer, flush=True)
	print(floating, flush=True)
	print(array, flush=True)
	print(table, flush=True)

	# print(string, file=sys.stderr, flush=True)
	# print(integer, file=sys.stderr, flush=True)
	# print(floating, file=sys.stderr, flush=True)
	# print(array, file=sys.stderr, flush=True)
	# print(table, file=sys.stderr, flush=True)


some_lambda = lambda: some_random_variables()
some_lambda()

def run_thread(duration: float):
	print("Sleeping thread for {}".format(duration))
	time.sleep(duration)

threads: List[Thread] = []
for i in range(1, 5):
	thread = Thread(name='Thread #{}'.format(i), target=run_thread, args=(i/2.0,))
	thread.start()
	threads.append(thread)

for thread in threads:
	thread.join()

raise Exception('Finished')
