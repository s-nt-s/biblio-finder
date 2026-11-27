import re
from urllib.parse import urljoin
import json

from requests import Session
from bs4 import BeautifulSoup, Tag
import logging
from typing import Union, Optional
from types import MappingProxyType

logger = logging.getLogger(__name__)

re_sp = re.compile(r"\s+")
re_emb = re.compile(r"^image/[^;]+;base64,.*", re.I)

default_headers = MappingProxyType({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Expires": "Thu, 01 Jan 1970 00:00:00 GMT",
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
    #'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
})


def iterhref(soup: BeautifulSoup):
    """Recorre los atributos href o src de los tags"""
    n: Tag
    for n in soup.find_all(["img", "form", "a", "iframe", "frame", "link", "script", "input"]):
        attrs = ("href", ) if n.name in ("a", "link") else ("src", "data-src")
        if n.name == "form":
            attrs = ("action", )
        for attr in attrs:
            val = n.attrs.get(attr)
            if val is None or re_emb.search(val):
                continue
            if not (val.startswith("#") or val.startswith("javascript:")):
                yield n, attr, val


def buildSoup(root: str, source: str, parser="lxml"):
    if source is None:
        return None
    soup = BeautifulSoup(source, parser)
    if root:
        for n, attr, val in iterhref(soup):
            val = urljoin(root, val)
            n.attrs[attr] = val
    return soup


def get_text(node: Tag | str, default: Optional[str] = None):
    if node is None:
        return default
    if isinstance(node, str):
        node = buildSoup(None, node)
    txt = None
    if node.name == "input":
        txt = node.attrs.get("value")
        if txt is None:
            txt = node.attrs.get("src")
    else:
        txt = node.get_text()
    if txt is None:
        return default
    if not isinstance(txt, str):
        raise ValueError(txt)
    txt = re_sp.sub(" ", txt).strip()
    if len(txt) == 0:
        return default
    return txt


def get_attr(node: Tag | str, attr: str, default: Optional[str] = None):
    if node is None:
        return default
    if isinstance(node, str):
        node = buildSoup(None, node)
    txt = node.attrs.get(attr)
    if txt is None:
        return default
    if not isinstance(txt, str):
        raise ValueError(txt)
    txt = re_sp.sub(" ", txt).strip()
    if len(txt) == 0:
        return default
    return txt


def refind(tag: Tag, slc: str, rgx: str) -> tuple[Tag]:
    arr: list[Tag] = []
    for n in tag.select(slc):
        txt = n.get_text().strip()
        if re.match(rgx, txt):
            arr.append(n)
    return tuple(arr)


class WebException(Exception):
    pass


class Web:
    def __init__(
        self,
        refer: str = None,
        verify: bool = True,
        headers: dict[str, str] = default_headers
    ):
        self.__s = Session()
        self.__s.headers = dict(headers)
        self.__response = None
        self.__soup = None
        self.__form = None
        self.__verify = verify
        self.__refer = refer

    def _get(
        self,
        url: str,
        allow_redirects: bool = True,
        auth=None,
        timeout=None,
        verify: Optional[bool] = None,
        **kwargs
    ):
        if verify is None:
            verify = self.__verify
        if kwargs:
            return self.__s.post(
                url,
                data=kwargs,
                timeout=timeout,
                allow_redirects=allow_redirects,
                verify=verify,
                auth=auth
            )
        return self.__s.get(
            url,
            allow_redirects=allow_redirects,
            timeout=timeout,
            verify=verify,
            auth=auth
        )

    def get_soup(
        self,
        url: str,
        auth=None,
        parser: str = "lxml",
        **kwargs
    ):
        r = self._get(url, auth=auth, **kwargs)
        return buildSoup(url, r.content, parser=parser)

    def get(
        self,
        url: str,
        auth=None,
        parser: str = "lxml",
        **kwargs
    ):
        if self.__refer:
            self.__s.headers.update({'referer': self.__refer})
        self.__response = self._get(url, auth=auth, **kwargs)
        self.__refer = self.__response.url
        self.__soup = buildSoup(url, self.__response.content, parser=parser)
        return self.__soup

    def prepare_submit(
        self,
        slc: str,
        silent_in_fail: bool = False,
        **kwargs
    ):
        data: dict[str, Union[str, int, float, None]] = {}
        self.__form = self.__soup.select_one(slc)
        if self.__form is None:
            if silent_in_fail:
                return None, None
            raise WebException(f"{slc} not found in {self.__url}")
        for i in self.__form.select("input[name]"):
            name = i.attrs["name"]
            data[name] = i.attrs.get("value")
        for i in self.__form.select("select[name]"):
            name = i.attrs["name"]
            slc = i.select_one("option[selected]")
            slc = slc.attrs.get("value") if slc else None
            data[name] = slc
        data = {**data, **kwargs}
        action: str = self.__form.attrs.get("action")
        action = action.rstrip() if action else None
        if action is None:
            action = self.__response.url
        return action, data

    def submit(
        self,
        slc: str,
        silent_in_fail: bool = False,
        **kwargs
    ):
        action, data = self.prepare_submit(
            slc, silent_in_fail=silent_in_fail, **kwargs)
        if silent_in_fail and not action:
            return None
        return self.get(action, **data)

    def val(self, slc):
        n = self.__soup.select_one(slc)
        if n is None:
            return None
        v = n.attrs.get("value", n.get_text())
        v = v.strip()
        return v if v else None

    @property
    def url(self):
        if self.__response is None:
            return None
        return self.__response.url

    def json(self, url, **kwargs):
        r = self._get(url, **kwargs)
        return r.json()

    def resolve(self, url, **kwargs):
        if self.refer:
            self.__s.headers.update({'referer': self.refer})
        r = self._get(url, allow_redirects=False, **kwargs)
        if r.status_code in (302, 301):
            return r.headers['location']

    def select_one(self, slc: str):
        n = self.__soup.select_one(slc)
        if n is None:
            raise WebException(f"{slc} NOT FOUND in {self.url}")
        return n

    def select_one_attr(self, slc: str, attr: str):
        n = self.select_one(slc)
        if attr not in n.attrs:
            raise WebException(f"{slc} has not {attr} in {self.url}")
        val = n.attrs[attr]
        if not isinstance(val, str):
            raise WebException(f"{slc} {attr}!=str in {self.url}")
        val = val.strip()
        if len(val) == 0:
            raise WebException(f"{slc} {attr} IS EMPTY in {self.url}")
        return val

    def select_one_txt(self, slc: str):
        n = self.select_one(slc)
        txt = get_text(n)
        if txt is None:
            raise WebException(f"{slc} IS EMPTY in {self.url}")
        return txt

    def select_one_json(self, slc: str) -> Union[dict, list]:
        txt = self.select_one_txt(slc)
        try:
            return json.loads(txt)
        except json.JSONDecodeError as e:
            raise WebException(f"{slc} no json in {self.__url} {e} {txt}")
