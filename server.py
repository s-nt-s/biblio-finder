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


def _ebiblio_urls() -> tuple[str, ...]:
    return tuple(
        url.strip()
        for url in os.environ.get("EBIBLIO_URL", "").split()
        if url.strip()
    )


S = Server(sys.argv[1])
F = Finder(*_ebiblio_urls())


@S.route("/search")
def search(title: str = None, author: str = None, lang: str = None):
    if title is None and author is None:
        raise ServerException(
            HTTPStatus.FORBIDDEN,
            "Parámetros incorrectos"
        )
    q = BookQuery(
        title=title,
        author=author,
        lang=lang or "spa"
    )
    books = F.search(q)
    return books


S.start()
