
from core.ebiblio import Ebiblio, SearchQuery
from core.model import BookQuery, Book, Source
from core.util import isLike, uq_add, uq_tp, get_longer


class Finder:
    def __init__(self, *ebiblio: str):
        self.__ebibilio = Ebiblio(*ebiblio)

    def __search_in_ebiblio(self, query: BookQuery):
        books: list[Book] = []
        for i in self.__ebibilio.search(SearchQuery(
            keywords=query.title,
            author=query.author,
            language=query.lang,
            medium="epub"
        )):
            if query.title and not isLike(query.title, i.title):
                continue
            author: list[str] = []
            for c in i.contributors:
                if c.role.lower() in ["autor", "author", "autores", "authors"]:
                    for n in c.names:
                        uq_add(author, n)
            b = Book(
                title=i.title,
                author=tuple(author),
                description=i.description,
                source=(Source(
                    url=i.url,
                    cover=i.cover_url
                ),)
            )
            if b not in books:
                books.append(b)
        return tuple(books)

    def search(self, query: BookQuery):
        ok: list[Book] = []
        for b in self.__search_in_ebiblio(query):
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
