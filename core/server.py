
import json
import logging
from dataclasses import is_dataclass, asdict
from http import HTTPStatus
from inspect import Parameter, signature
from wsgiref.types import StartResponse, WSGIEnvironment
from typing import Callable, NamedTuple, Optional
from urllib.parse import parse_qs
from types import MappingProxyType

from waitress import serve

logger = logging.getLogger(__name__)


def _jsonable(value):
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, set):
        value = sorted(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


class ServerException(Exception):
    def __init__(
        self,
        http_status: int,
        msg: str,
        code: Optional[int] = None,
    ):
        self.__http_status = http_status
        self.__code = http_status if code is None else code
        self.__msg = msg
        super().__init__(f"{self.__code} {msg}")

    @property
    def http_status(self):
        return self.__http_status

    @property
    def code(self):
        return self.__code

    @property
    def msg(self):
        return self.__msg


class Rq(NamedTuple):
    method: str
    path: str
    query: MappingProxyType


class Server:
    def __init__(self, listen: str):
        host, port = listen.split(":")
        self.__host = host
        self.__port = int(port)
        self.__routes: dict[str, Callable[..., object]] = {}

    def route(self, path: str):
        """Register a GET endpoint using Flask-style decorator syntax."""
        if not path.startswith("/"):
            path = f"/{path}"

        def decorator(function):
            if path in self.__routes:
                raise ValueError(
                    f"A route is already registered for {path!r}."
                )
            self.__routes[path] = function
            return function

        return decorator

    @staticmethod
    def __get_reason(status: int):
        try:
            return HTTPStatus(status).phrase
        except ValueError:
            return "Unknown Status"

    @staticmethod
    def __cors_headers():
        return [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, OPTIONS"),
            ("Access-Control-Allow-Headers", "*"),
        ]

    @staticmethod
    def __response(
        start_response: StartResponse,
        status: int,
        payload,
        extra_headers=(),
    ):
        reason = Server.__get_reason(status)
        body = json.dumps(
            _jsonable(payload),
            ensure_ascii=False
        ).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ]
        headers.extend(Server.__cors_headers())
        headers.extend(extra_headers)
        start_response(
            f"{status} {reason}",
            headers
        )
        return [body]

    @staticmethod
    def __invoke(function, query: dict):
        parameters = signature(function).parameters
        accepts_extra = any(
            parameter.kind is Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        kwargs = {
            key: values[0]
            for key, values in query.items()
            if accepts_extra
            or (
                key in parameters
                and parameters[key].kind in (
                    Parameter.POSITIONAL_OR_KEYWORD,
                    Parameter.KEYWORD_ONLY,
                )
            )
        }
        return function(**kwargs)

    def __build_app(self):
        def application(
            environ: WSGIEnvironment,
            start_response: StartResponse,
        ):
            rq = Rq(
                method=environ.get("REQUEST_METHOD", ""),
                path=environ.get("PATH_INFO", "/"),
                query=parse_qs(environ.get("QUERY_STRING", "")),
            )
            if rq.method == "OPTIONS":
                start_response(
                    "204 No Content",
                    [("Content-Length", "0")]
                    + Server.__cors_headers()
                )
                return []
            if rq.method != "GET":
                return self.__response(
                    start_response,
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    {"msg": "Method Not Allowed"},
                    (("Allow", "GET, OPTIONS"),),
                )

            function = self.__routes.get(rq.path)
            if function is None:
                return self.__response(
                    start_response,
                    HTTPStatus.NOT_FOUND,
                    {
                        "msg":
                        f"Not Found: {rq.path}"
                    },
                )

            try:
                result = self.__invoke(function, rq.query)
                return self.__response(
                    start_response,
                    HTTPStatus.OK,
                    result,
                )
            except ServerException as exception:
                return self.__response(
                    start_response,
                    exception.http_status,
                    {"code": exception.code, "msg": exception.msg},
                )
            except Exception as exception:
                logger.exception("Error while processing route %s", rq.path)
                return self.__response(
                    start_response,
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"msg": str(exception)},
                )

        return application

    def start(self):
        logger.info("Available routes:")
        for path in self.__routes:
            logger.info("GET %s", path)
        serve(
            self.__build_app(),
            host=self.__host,
            port=self.__port
        )
