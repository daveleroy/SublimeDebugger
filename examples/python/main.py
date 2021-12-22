import time
import sys

from threading import Thread
from typing import List

print(sys.version)
# print(os.environ)

def some_random_variables():
	string = "abc"
	integer = 1
	floating = 2.345
	array = [string, integer, floating]
	table = {
		'string': string,
		'intger': integer,
		'float': floating,
		'array': array,
	}

	print(string)
	print(integer)
	print(floating)
	print(array)
	print(table)


def test():
	some_random_variables()

def sleep(duration: float):
	print("Sleeping thread for {}".format(duration))
	time.sleep(duration)

threads: List[Thread] = []

for i in range(1, 5):
	thread = Thread(name='Thread #{}'.format(i), target=sleep, args=(i/2.0,))
	thread.start()
	threads.append(thread)

some_lambda = lambda: test()
some_lambda()
for thread in threads:
	thread.join()


print('Done')

