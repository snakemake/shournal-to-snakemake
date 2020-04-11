
import sys

def eprint(*args, **kwargs):
    """
    print-to-stderr-shortcut with the same signature as 'print'
    """
    print(*args, file=sys.stderr, **kwargs)


def is_subpath(path2Test, path_, allowEquals=False):
    """
    Check if path2Test is a sub-path of path.
    Only for clean, absolute (unix) paths without trailing /. No filesystem-access involved!
    """
    assert path2Test[-1] != '/' and path_[-1] != '/'
    if allowEquals and path2Test == path_:
        return True
    return path2Test.startswith(path_ + '/')



class SimpleJsonToObject:
    """
    Store one level of json within this object.
    Note that nested arrays are *not* resolved.
    """
    def __init__(self, rawJson):
        self.__dict__ = rawJson




