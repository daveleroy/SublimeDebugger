import time
from threading import Thread
import sys

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

	sys.stdout.write('Hello from stdout\n')
	sys.stderr.write('Hello from stderr\n')

def test():
	some_random_variables()

def sleep(duration):
	print("Sleeping thread for {}".format(duration))
	time.sleep(duration)

threads = []
for i in range(1, 5):
	thread = Thread(name='Thread #{}'.format(i), target=sleep, args=(i/2.0,))
	thread.start()
	threads.append(thread)

some_lambda = lambda: test()
some_lambda()

for thread in threads:
	thread.join()


print('Done')
