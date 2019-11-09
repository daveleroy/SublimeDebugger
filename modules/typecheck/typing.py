
TYPE_CHECKING = False


class Any:
    pass

class Protocol:
    pass

class _GetAttr(type):
    def __getitem__(self, x):
        return self


class Generic(metaclass=_GetAttr):
    pass


class Generator(Generic):
    pass


class Callable(Generic):
    pass


class List(Generic):
    pass


class Optional(Generic):
    pass


class Tuple(Generic):
    pass


class Union(Generic):
    pass


class Dict(Generic):
    pass


class Set(Generic):
    pass


class Sequence(Generic):
    pass


class NamedTuple(Generic):
    pass


class TypeVar:
    def __init__(self, name: str) -> None:
        pass
