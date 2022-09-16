from multiprocessing import Pool
import time


def f(x):
    print(f'sleep: {x}')
    time.sleep(x)
    print(f'awake: {x}')
    return x*x

if __name__ == '__main__':
    with Pool(5) as p:
        print('spawed subprocesses')
        print(p.map(f, [1, 2, 3]))