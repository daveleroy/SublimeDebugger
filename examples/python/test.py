import time
from threading import Thread
import sys

a = "abc"
b = 123
c = 123.123

print(a)
print(b)
print(c)

sys.stderr.write('Testing standard error output')

def outFunction(i):
      innerFunction(i + 2)
      print("Thread exiting")
def innerFunction(i):
      print("Sleeping thread for {}".format(i))
      time.sleep(i)


t1 = Thread(target = outFunction, args = (1,))
t1.start()
t2 = Thread(target = outFunction, args = (2,))
t2.start()
t3 = Thread(target = outFunction, args = (3,))
t3.start()

t1.join()
t2.join()
t3.join()

print('Done')

