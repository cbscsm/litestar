from dataclasses import MISSING
from inspect import Signature
from typing import Final

from msgspec import UnsetType

from litestar.enums import MediaType
from litestar.types import Empty

DEFAULT_ALLOWED_CORS_HEADERS: Final = {"Accept", "Accept-Language", "Content-Language", "Content-Type"}
DEFAULT_CHUNK_SIZE: Final = 1024 * 128  # 128KB
HTTP_DISCONNECT: Final = "http.disconnect"
HTTP_RESPONSE_BODY: Final = "http.response.body"
HTTP_RESPONSE_START: Final = "http.response.start"
ONE_MEGABYTE: Final = 1024 * 1024
OPENAPI_NOT_INITIALIZED: Final = "Litestar has not been instantiated with OpenAPIConfig"
REDIRECT_STATUS_CODES: Final = {301, 302, 303, 307, 308}
REDIRECT_ALLOWED_MEDIA_TYPES: Final = {MediaType.TEXT, MediaType.HTML, MediaType.JSON}
RESERVED_KWARGS: Final = {"state", "headers", "cookies", "request", "socket", "data", "query", "scope", "body"}
SCOPE_STATE_BASE_URL_KEY = "base_url"
SCOPE_STATE_COOKIES_KEY = "cookies"
SCOPE_STATE_CSRF_TOKEN_KEY = "csrf_token"  # noqa: S105  # possible hardcoded password
SCOPE_STATE_DEPENDENCY_CACHE: Final = "dependency_cache"
SCOPE_STATE_DO_CACHE: Final = "do_cache"
SCOPE_STATE_IS_CACHED: Final = "is_cached"
SCOPE_STATE_NAMESPACE: Final = "__litestar__"
SCOPE_STATE_PARSED_QUERY_KEY = "parsed_query"
SCOPE_STATE_RESPONSE_COMPRESSED: Final = "response_compressed"
SCOPE_STATE_URL_KEY = "url"
SKIP_VALIDATION_NAMES: Final = {"request", "socket", "scope", "receive", "send"}
UNDEFINED_SENTINELS: Final = {Signature.empty, Empty, Ellipsis, MISSING, UnsetType}
WEBSOCKET_CLOSE: Final = "websocket.close"
WEBSOCKET_DISCONNECT: Final = "websocket.disconnect"
