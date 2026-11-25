from ebiblio import EbiblioClient, SearchQuery, SearchResult
from core.model import Book, BookQuery, Source
from core.util import isLike, uq_add


class Ebiblio:
    def __init__(self, *urls):
        self.__clients = tuple(map(EbiblioClient, urls))

    def __search(self, query: SearchQuery):
        result: list[SearchResult] = []
        for c in self.__clients:
            for r in c.search_all(query):
                if r not in result:
                    result.append(r)
        return tuple(result)

    def search(self, query: BookQuery):
        books: list[Book] = []
        for i in self.__search(SearchQuery(
            title=query.title,
            author=query.author,
            language=query.lang,
            medium="epub",
            nature="ebook"
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
                    cover=i.cover_url.replace("size=large", "size=small")
                ),)
            )
            if b not in books:
                books.append(b)
        return tuple(books)
