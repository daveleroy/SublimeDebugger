import time
from threading import Thread
import sys

a = 1
b = 2

print('standard output!')
sys.stderr.write('standard error output!')

def func(i):
	while True:
		pass

def outer(i):
	if i == 0:
		func(i)
	outer(i - 1)

t1 = Thread(target = outer, args = (1,))
t1.start()
t2 = Thread(target = outer, args = (5,))
t2.start()
t3 = Thread(target = outer, args = (8,))
t3.start()

t1.join()
t2.join()
t3.join()

# time.sleep(1)
print('done')

