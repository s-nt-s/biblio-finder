from opac import OpacClient, SearchQuery, SearchResult
from core.model import Book, BookQuery, Source
from core.util import isLike
from os import environ


class Opac:
    def __init__(self, *urls):
        self.__clients = tuple(map(lambda x: OpacClient(
            x,
            proxy=environ.get("OPAC_PROXY")
        ), urls))

    def __search(self, query: SearchQuery):
        result: list[SearchResult] = []
        for c in self.__clients:
            rt = c.search(query)
            for r in rt.items:
                if r not in result:
                    result.append(r)
        return tuple(result)

    def search(self, query: BookQuery):
        LANG = {
            "spa": "02"
        }
        books: list[Book] = []
        for i in self.__search(SearchQuery(
            title=query.title,
            author=query.author,
            language=LANG.get(query.lang),
            medium="1",  # Libros
            items_per_page=100
        )):
            if query.title and not isLike(query.title, i.title):
                continue
            b = Book(
                title=i.title,
                author=(i.author, ) if i.author else (),
                description=i.description or "",
                source=(Source(
                    url=i.url,
                    cover=i.cover_url
                ),)
            )
            if b not in books:
                books.append(b)
        return tuple(books)
