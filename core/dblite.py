
import sqlite3
from sqlite3 import InterfaceError, OperationalError
from os.path import isfile
from os import remove
from collections import defaultdict
import logging
from pathlib import Path
from collections.abc import Callable

logger = logging.getLogger(__name__)


def gW(tp: tuple):
    if len(tp) == 0:
        return None
    if len(tp) == 1:
        return "= ?"
    prm = ", ".join(['?'] * len(tp))
    return f"in ({prm})"


class DBlite:
    def __init__(
        self,
        file: str | Path,
        reload: bool = False,
        readonly: bool = False
    ):
        self.__file = str(file)
        if reload and readonly:
            raise ValueError("reload=True no es compatible con readonly=True")
        if reload and isfile(self.__file):
            remove(self.__file)
        self.__con = None
        self.__many: dict[str, list[tuple]] = defaultdict(list)
        self.__readonly = readonly

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    @property
    def file(self):
        return self.__file

    @property
    def con(self):
        if self.__con is None:
            logger.info(f"Connecting to {self.__file}")
            if self.__readonly:
                uri = Path(self.__file).resolve().as_uri() + "?mode=ro"
                self.__con = sqlite3.connect(uri, uri=True)
            else:
                self.__con = sqlite3.connect(self.__file)
        return self.__con

    def execute(self, sql: str, *args, log_level: int = None):
        if log_level is not None:
            logger.log(log_level, sql)
        r = self.con.execute(sql, args)
        if log_level is not None:
            logger.log(log_level, f"└ {r.rowcount} items")
        return r

    def create_function(
        self,
        name: str,
        narg: int,
        func: Callable[..., object],
        *,
        deterministic: bool = False,
    ) -> None:
        """Registra una función Python para usarla en consultas SQL."""
        self.con.create_function(
            name,
            narg,
            func,
            deterministic=deterministic,
        )

    def executescript(self, sql: str):
        return self.con.executescript(sql)

    def executemany(self, sql: str, vals: tuple):
        self.__many[sql].append(vals)
        if len(self.__many[sql]) < 1000:
            return None
        r = self.con.executemany(sql, self.__many[sql])
        del self.__many[sql]
        return r

    def select(self, sql: str, *args, **kwargs):
        c = self.con.cursor()
        try:
            if len(args):
                c.execute(sql, args)
            else:
                c.execute(sql)
        except OperationalError:
            logger.critical(sql)
            c.close()
            raise
        columns = tuple(column[0] for column in c.description)
        try:
            for row in c:
                yield dict(zip(columns, row))
        finally:
            c.close()

    def one(self, sql: str, *args):
        cursor = self.con.cursor()
        if len(args):
            cursor.execute(sql, args)
        else:
            cursor.execute(sql)
        r = cursor.fetchone()
        cursor.close()
        if not r:
            return None
        if isinstance(r, (tuple, list)) and len(r) == 1:
            return r[0]
        return r

    def to_tuple(self, *args, **kwargs):
        arr = []
        for row in self.select(*args, **kwargs):
            values = tuple(row.values())
            arr.append(values[0] if len(values) == 1 else values)
        return tuple(arr)

    def get_dict(self, *args, **kwargs):
        obj = dict()
        for row in self.select(*args, **kwargs):
            key, value = row.values()
            obj[key] = value
        return obj

    def flush(self):
        for sql, vals in self.__many.items():
            try:
                self.con.executemany(sql, vals)
            except InterfaceError:
                logger.critical(f"{sql} % {vals}")
                raise
        self.__many.clear()

    def commit(self):
        self.con.commit()

    def close(self):
        if self.__con is None:
            return
        logger.info(f"Closing {self.__file}")
        self.commit()
        if not self.__readonly:
            c = self.execute("pragma integrity_check").fetchone()
            c = c[0] if c and len(c) == 1 else c
            if c == 'ok':
                logger.info("[OK] integrity_check")
            else:
                logger.warning("[KO] integrity_check = " + (c or "¿?"))
            c = self.execute("pragma foreign_key_check").fetchall()
            if not c:
                logger.info("[OK] foreign_key_check")
            else:
                logger.warning("[KO] foreign_key_check")
                for table, parent in set((i[0], i[2]) for i in c):
                    logger.warning(f"  {table} -> {parent}")
            logger.info(f"Vacuum {self.__file}")
            self.execute("VACUUM")
            self.commit()
        self.__con.close()
        self.__con = None
