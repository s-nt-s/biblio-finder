
from core.ebiblio import Ebiblio
from core.model import BookQuery, Book
from core.util import uq_add, uq_tp, get_longer
from core.epublibre import EpubLibre
from core.opac import Opac
from core.casaencendida import CasaEncendida


class Finder:
    def __init__(self, ebiblio: tuple[str, ...] = (), opac: tuple[str, ...] = ()):
        self.__ebibilio = Ebiblio(*ebiblio)
        self.__epublibre = EpubLibre()
        self.__opac = Opac(*opac)
        self.__casaencendida = CasaEncendida()

    def __iter_search(self, query: BookQuery):
        if query.format in ("epub", None):
            for b in self.__ebibilio.search(query):
                yield b
            for b in self.__epublibre.search(query):
                yield b
        if query.format in ("paper", None):
            for b in self.__opac.search(query):
                yield b
        for b in self.__casaencendida.search(query):
            yield b

    def search(self, query: BookQuery):
        ok: list[Book] = []
        for b in self.__iter_search(query):
            index = next(
                (i for i, x in enumerate(ok) if x.is_like(b)),
                None
            )
            if index is None:
                uq_add(ok, b)
                continue
            book = ok[index]
            book = book._replace(
                title=get_longer(book.title, b.title),
                description=get_longer(book.description, b.description),
                author=uq_tp(*book.author, *b.author),
                source=uq_tp(*book.source, *b.source)
            )
            ok[index] = book
        return tuple(ok)
