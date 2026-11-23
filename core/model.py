from typing import NamedTuple, Optional
from core.util import isLike, simplify


class BookQuery(NamedTuple):
    title: Optional[str] = None
    author: Optional[str] = None
    lang: Optional[str] = None


class Source(NamedTuple):
    url: str
    cover: str


class Book(NamedTuple):
    title: str
    description: str
    author: tuple[str, ...]
    source: tuple[Source, ...]

    def is_like(self, o: "Book"):
        if not isLike(self.title, o.title, lax=True):
            return False
        if len(self.description) > 100 and len(o.description) > 100:
            if isLike(self.description, o.description, lax=True):
                return True
        a1 = set(map(simplify, self.author))
        a2 = set(map(simplify, o.author))
        if len(a1.intersection(a2)):
            return True
        return False