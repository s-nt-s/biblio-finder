from urllib.parse import urlencode

from core.web import Web, get_text
from core.model import BookQuery, Book, Source
import re


def _clean_title(title: str):
    title = re.sub(r"\s+/\s+.*$", "", title)
    return title


class CasaEncendida:
    URL = "https://bibliotecas.montemadrid.es/vufind/Search/Results"

    def __init__(self):
        self.__w = Web()

    def search(self, query: BookQuery):
        if query.format is None:
            a = self.search(query._replace(format="epub"))
            b = self.search(query._replace(format="paper"))
            return a + b
        params: list[tuple[str, str]] = [
            ('join', 'AND'),
            ('bool0[]', 'AND'),
            ('limit', '100'),
        ]
        if query.title:
            params.append(('lookfor0[]', query.title))
            params.append(('type0[]', 'Title'))
        if query.author:
            params.append(('lookfor0[]', query.author))
            params.append(('type0[]', 'Author'))
        lang = {
            "span": "Spanish"
        }.get(query.lang)
        if lang:
            params.append(('filter[]', f'~language:"{lang}"'))
        frmt = {
            "epub": "eBook",
            "paper": "Book"
        }.get(query.format)
        if frmt:
            params.append(('filter[]', f'~format:"{frmt}"'))
        url = f"{CasaEncendida.URL}?{urlencode(params)}"
        books: list[Book] = []
        while True:
            soup = self.__w.get(url)
            print(url)
            for row in soup.select("#result div.row"):
                a = row.select_one("h4 a")
                author = []
                for x in map(get_text, row.select("a[id^=book-author]")):
                    if x and x not in author:
                        author.append(x)
                img = row.select_one("img.recordcover")
                b = Book(
                    title=_clean_title(get_text(a)),
                    description="",
                    author=tuple(author),
                    source=(Source(
                        url=a.attrs["href"],
                        cover=img.attrs["src"] if img else None
                    ),)
                )
                if b not in books:
                    books.append(b)
            nxt = soup.select_one("a.page-link")
            if nxt is None:
                return tuple(books)
            url = nxt.attrs.get("href")
