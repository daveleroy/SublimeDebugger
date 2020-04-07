import sys
import subprocess
import ctypes
import ctypes.util


class StructRLimit(ctypes.Structure):
    _fields_ = [('rlim_cur', ctypes.c_ulong), ('rlim_max', ctypes.c_ulong)]


if sys.platform == "darwin":
    RLIMIT_NOFILE = 8
else:
    RLIMIT_NOFILE = 7


def _getgetrlimit(resource):
    try:
        limits = StructRLimit()
        libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
        libc.getrlimit(resource, ctypes.byref(limits))
        return (limits.rlim_cur, limits.rlim_max)
    except Exception:
        # better than error !?
        return (10000, None)


def getrlimit(resource):
    if resource == RLIMIT_NOFILE:
        try:
            soft_limit = int(subprocess.check_output(
                ['sh', '-c', 'ulimit -Sn'], stderr=subprocess.PIPE))
        except Exception:
            soft_limit = _getgetrlimit(resource)[0]
        hard_limit = None
        return (soft_limit, hard_limit)
