"""Production WSGI server for book searches."""

import logging
import os

from core.finder import Finder
from core.model import BookQuery
from core.server import Server, ServerException
from http import HTTPStatus
from core.epublibre import EpubLibre
import sys


LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_tuple(name: str) -> tuple[str, ...]:
    return tuple(
        url.strip()
        for url in os.environ.get(name, "").split()
        if url.strip()
    )


S = Server(sys.argv[1])
F = Finder(
    ebiblio=get_tuple("EBIBLIO_URL"),
    opac=get_tuple("OPAC_URL")
)


@S.route("/search")
def search(title: str = None, author: str = None, lang: str = None, format: str = None):
    if title is None and author is None:
        raise ServerException(
            HTTPStatus.FORBIDDEN,
            "Parámetros incorrectos"
        )
    q = BookQuery(
        title=title,
        author=author,
        lang=lang or "spa",
        format=format
    )
    books = F.search(q)
    return books


S.start()
