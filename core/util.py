
from unidecode import unidecode
import re
from dataclasses import is_dataclass, asdict

re_sp = re.compile(r"\s+")


def parse_obj(value):
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: parse_obj(item) for key, item in value.items()}
    if isinstance(value, set):
        value = sorted(value)
    if isinstance(value, (list, tuple)):
        return [parse_obj(item) for item in value]
    return value


def simplify(s: str):
    s = re_sp.sub(" ", s).strip()
    s = unidecode(s.lower())
    return s


def isLike(a: str, *others: str, lax: bool = False):
    a = simplify(a)
    for b in map(simplify, others):
        if a == b or a in b:
            return True
        if lax and b in a:
            return True
    return False


def uq_add(arr: list, o):
    if o is not None and o not in arr:
        return arr.append(o)


def uq_tp(*args):
    arr = []
    for x in args:
        uq_add(arr, x)
    return tuple(arr)


def get_longer(*args: str):
    x = ''
    for a in args:
        if len(a) > len(x):
            x = a
    return x