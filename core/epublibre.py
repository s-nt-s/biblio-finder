import csv
import io
from zipfile import ZipFile
from typing import NamedTuple
import requests
import re
from core.filemanager import FM
from core.dblite import DBlite
import logging
from tempfile import NamedTemporaryFile
from pathlib import Path
from core.model import BookQuery, Book, Source
from core.util import simplify, uq_tp


logger = logging.getLogger(__name__)

re_sp = re.compile(r"\s+")


def _parse(s: str):
    s = s.replace("\u2028", "\n\n")
    s = s.replace("\u2029", "\n\n")
    s = re.sub(r"  +", " ", s)
    s = re.sub(r"\n\s*\n\s*\n", "\n\n", s)
    s = s.strip()
    return s


class ELBook(NamedTuple):
    id: int
    title: str
    author: str
    description: str
    language: str

    @classmethod
    def build(cls, obj: dict):
        obj = {k: obj.get(k) for k in cls._fields}
        return cls(**obj)


class EpubLibre:
    DB: Path = FM.resolve_path("cache/epublibre.db")
    URL = "http://rss.epublibre.org/csv"
    TOR_PROXY = "socks5h://127.0.0.1:9050"
    KO_LANG = (
        'Euskera',
        'Catalán',
        'Francés',
        'Sueco',
        'Esperanto',
        'Italiano',
        'Portugués',
        'Gallego',
        'Mandarín'
    )
    OK_LANG = {
        'Español': "spa",
        'Inglés': "eng",
        'Alemán': "ger"
    }

    @staticmethod
    def iter_books():
        proxies = {
            "http": EpubLibre.TOR_PROXY,
            "https": EpubLibre.TOR_PROXY,
        }
        with requests.get(EpubLibre.URL, proxies=proxies) as r:
            r.raise_for_status()
            with ZipFile(io.BytesIO(r.content)) as z:
                files = [
                    item.filename
                    for item in z.infolist()
                    if not item.is_dir()
                ]
                csv_file = files[0] if len(files) == 1 and files[0].lower().endswith(".csv") else None
                if csv_file is None:
                    raise ValueError(
                        "El ZIP debe contener exactamente un fichero CSV"
                    )
                with io.TextIOWrapper(
                    z.open(csv_file),
                    encoding="utf-8-sig",
                    newline="",
                ) as csv_body:
                    for row in csv.DictReader(csv_body):
                        votes = int(row['Nº Votos'])
                        if votes < 5:
                            continue
                        rate = float(row['Valoración'].replace(",", "."))
                        if rate < 4:
                            continue
                        lang = row['Idioma']
                        if lang in EpubLibre.KO_LANG:
                            continue
                        if lang not in EpubLibre.OK_LANG:
                            logger.critical("Idioma desconocido "+lang)
                            continue
                        lang = EpubLibre.OK_LANG[lang]
                        yield ELBook(
                            id=int(row['EPL Id']),
                            title=re_sp.sub(" ", row['Título']).strip(),
                            description=_parse(row['Sinopsis']),
                            author=row['Autor'],
                            language=lang
                        )

    @staticmethod
    def create_db():
        create = FM.load("rec/epublibre.sql")
        EpubLibre.DB.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            suffix=".db",
            dir=EpubLibre.DB.parent,
        ) as tmp:
            TMP = Path(tmp.name)
            with DBlite(TMP) as db:
                db.executescript(create)
                for b in EpubLibre.iter_books():
                    db.executemany(
                        """
                        INSERT into EPUB (
                        id, title, description, author, language,
                        simply_title, simply_author
                        )
                        values (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            b.id, b.title, b.description, b.author, b.language,
                            simplify(b.title), simplify(b.author)
                        )
                    )
                db.flush()
            tmp.flush()
            TMP.replace(EpubLibre.DB)

    @staticmethod
    def get_db():
        if not EpubLibre.DB.is_file():
            EpubLibre.create_db()
        return EpubLibre.DB

    def search(self, query: BookQuery):
        args: list[str] = []
        where: list[str] = []
        fts_terms: list[str] = []

        if query.lang:
            where.append("e.language = ?")
            args.append(query.lang)

        if query.title:
            title = simplify(query.title)
            if len(title) >= 3:
                phrase = title.replace('"', '""')
                fts_terms.append(f'simply_title : "{phrase}"')
            else:
                where.append("instr(e.simply_title, ?) > 0")
                args.append(title)

        if query.author:
            author = simplify(query.author)
            if len(author) >= 3:
                phrase = author.replace('"', '""')
                fts_terms.append(f'simply_author : "{phrase}"')
            else:
                where.append("instr(e.simply_author, ?) > 0")
                args.append(author)

        if fts_terms:
            where.append(
                "e.id IN (SELECT rowid FROM EPUB_FTS WHERE EPUB_FTS MATCH ?)"
            )
            args.append(" AND ".join(fts_terms))

        if not where:
            raise ValueError("Hace falta al menos una condición where")

        sql = "SELECT e.* FROM EPUB AS e WHERE " + " AND ".join(where)
        result: list[Book] = []
        with DBlite(EpubLibre.get_db(), readonly=True) as db:
            for r in db.select(sql, *args):
                b = Book(
                    title=r['title'],
                    description=r['description'],
                    author=uq_tp(*re.split(r"\s+&\s+", r['author'])),
                    source=(Source(
                        url=f"https://www.epublibre.org/libro/detalle/{r['id']}",
                        cover=f"https://images.epublibre.org/libros/{r['id']}.jpg"
                    ),)
                )
                result.append(b)
        return tuple(result)


if __name__ == "__main__":
    EpubLibre.create_db()
