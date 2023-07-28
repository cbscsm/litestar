# ruff: noqa: UP006
from __future__ import annotations

import re
from functools import partial
from pathlib import Path, PurePath
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Literal,
    Optional,
    Sequence,
    Set,
    TypedDict,
    Union,
    cast,
)
from uuid import UUID

from msgspec import NODEFAULT, Meta, Struct, ValidationError, convert, defstruct
from msgspec.structs import asdict
from typing_extensions import Annotated

from litestar._signature.types import ExtendedMsgSpecValidationError
from litestar._signature.utils import (
    _get_decoder_for_type,
    _normalize_annotation,
    _validate_signature_dependencies,
)
from litestar.datastructures import ImmutableState
from litestar.enums import ParamType, ScopeType
from litestar.exceptions import InternalServerException, ValidationException
from litestar.params import KwargDefinition, ParameterKwarg
from litestar.typing import FieldDefinition  # noqa
from litestar.utils import is_class_and_subclass
from litestar.utils.dataclass import simple_asdict

if TYPE_CHECKING:
    from typing_extensions import NotRequired

    from litestar.connection import ASGIConnection
    from litestar.types import AnyCallable, TypeDecodersSequence
    from litestar.utils.signature import ParsedSignature

__all__ = (
    "ErrorMessage",
    "SignatureModel",
)


class ErrorMessage(TypedDict):
    # key may not be set in some cases, like when a query param is set but
    # doesn't match the required length during `attrs` validation
    # in this case, we don't show a key at all as it will be empty
    key: NotRequired[str]
    message: str
    source: NotRequired[Literal["body"] | ParamType]


MSGSPEC_CONSTRAINT_FIELDS = (
    "gt",
    "ge",
    "lt",
    "le",
    "multiple_of",
    "pattern",
    "min_length",
    "max_length",
)

ERR_RE = re.compile(r"`\$\.(.+)`$")

DEFAULT_TYPE_DECODERS = [
    (lambda x: is_class_and_subclass(x, (Path, PurePath, ImmutableState, UUID)), lambda t, v: t(v))
]


def _deserializer(target_type: Any, value: Any, default_deserializer: Callable[[Any, Any], Any]) -> Any:
    if isinstance(value, target_type):
        return value

    if hasattr(target_type, "_decoder"):
        return target_type._decoder(target_type, value)

    return default_deserializer(target_type, value)


class SignatureModel(Struct):
    """Model that represents a function signature that uses a msgspec specific type or types."""

    # NOTE: we have to use Set and Dict here because python 3.8 goes haywire if we use 'set' and 'dict'
    _dependency_name_set: ClassVar[Set[str]]
    _fields: ClassVar[Dict[str, FieldDefinition]]
    _return_annotation: ClassVar[Any]

    @classmethod
    def _create_exception(cls, connection: ASGIConnection, messages: list[ErrorMessage]) -> Exception:
        """Create an exception class - either a ValidationException or an InternalServerException, depending on whether
            the failure is in client provided values or injected dependencies.

        Args:
            connection: An ASGI connection instance.
            messages: A list of error messages.

        Returns:
            An Exception
        """
        method = connection.method if hasattr(connection, "method") else ScopeType.WEBSOCKET  # pyright: ignore
        if client_errors := [
            err_message
            for err_message in messages
            if ("key" in err_message and err_message["key"] not in cls._dependency_name_set) or "key" not in err_message
        ]:
            return ValidationException(detail=f"Validation failed for {method} {connection.url}", extra=client_errors)
        return InternalServerException()

    @classmethod
    def _build_error_message(cls, keys: Sequence[str], exc_msg: str, connection: ASGIConnection) -> ErrorMessage:
        """Build an error message.

        Args:
            keys: A list of keys.
            exc_msg: A message.
            connection: An ASGI connection instance.

        Returns:
            An ErrorMessage
        """

        message: ErrorMessage = {"message": exc_msg.split(" - ")[0]}

        if keys:
            message["key"] = key = ".".join(keys)
            if keys[0].startswith("data"):
                message["key"] = message["key"].replace("data.", "")
                message["source"] = "body"
            elif key in connection.query_params:
                message["source"] = ParamType.QUERY

            elif key in cls._fields and isinstance(cls._fields[key].kwarg_definition, ParameterKwarg):
                if cast(ParameterKwarg, cls._fields[key].kwarg_definition).cookie:
                    message["source"] = ParamType.COOKIE
                elif cast(ParameterKwarg, cls._fields[key].kwarg_definition).header:
                    message["source"] = ParamType.HEADER
                else:
                    message["source"] = ParamType.QUERY

        return message

    @classmethod
    def _collect_errors(cls, deserializer: Callable[[Any, Any], Any], **kwargs: Any) -> list[tuple[str, Exception]]:
        exceptions: list[tuple[str, Exception]] = []
        for field_name in cls._fields:
            try:
                raw_value = kwargs[field_name]
                annotation = cls.__annotations__[field_name]
                convert(raw_value, type=annotation, strict=False, dec_hook=deserializer, str_keys=True)
            except Exception as e:  # noqa: BLE001
                exceptions.append((field_name, e))

        return exceptions

    @classmethod
    def parse_values_from_connection_kwargs(cls, connection: ASGIConnection, **kwargs: Any) -> dict[str, Any]:
        """Extract values from the connection instance and return a dict of parsed values.

        Args:
            connection: The ASGI connection instance.
            **kwargs: A dictionary of kwargs.

        Raises:
            ValidationException: If validation failed.
            InternalServerException: If another exception has been raised.

        Returns:
            A dictionary of parsed values
        """
        messages: list[ErrorMessage] = []
        deserializer = partial(_deserializer, default_deserializer=connection.route_handler.default_deserializer)
        try:
            return convert(kwargs, cls, strict=False, dec_hook=deserializer, str_keys=True).to_dict()
        except ExtendedMsgSpecValidationError as e:
            for exc in e.errors:
                keys = [str(loc) for loc in exc["loc"]]
                message = cls._build_error_message(keys=keys, exc_msg=exc["msg"], connection=connection)
                messages.append(message)
            raise cls._create_exception(messages=messages, connection=connection) from e
        except ValidationError as e:
            for field_name, exc in cls._collect_errors(deserializer=deserializer, **kwargs):  # type: ignore[assignment]
                match = ERR_RE.search(str(exc))
                keys = [field_name, str(match.group(1))] if match else [field_name]
                message = cls._build_error_message(keys=keys, exc_msg=str(e), connection=connection)
                messages.append(message)
            raise cls._create_exception(messages=messages, connection=connection) from e

    def to_dict(self) -> dict[str, Any]:
        """Normalize access to the signature model's dictionary method, because different backends use different methods
        for this.

        Returns: A dictionary of string keyed values.
        """
        return asdict(self)

    @classmethod
    def create(
        cls,
        dependency_name_set: set[str],
        fn: AnyCallable,
        has_data_dto: bool,
        parsed_signature: ParsedSignature,
        type_decoders: TypeDecodersSequence,
    ) -> type[SignatureModel]:
        fn_name = (
            fn_name if (fn_name := getattr(fn, "__name__", "anonymous")) and fn_name != "<lambda>" else "anonymous"
        )

        dependency_names = _validate_signature_dependencies(
            dependency_name_set=dependency_name_set, fn_name=fn_name, parsed_signature=parsed_signature
        )

        struct_fields: list[tuple[str, Any, Any]] = []

        for field_definition in parsed_signature.parameters.values():
            meta_data: Meta | None = None

            if isinstance(field_definition.kwarg_definition, KwargDefinition):
                meta_kwargs: dict[str, Any] = {"extra": {}}

                kwarg_definition = simple_asdict(field_definition.kwarg_definition, exclude_empty=True)
                if min_items := kwarg_definition.pop("min_items", None):
                    meta_kwargs["min_length"] = min_items
                if max_items := kwarg_definition.pop("max_items", None):
                    meta_kwargs["max_length"] = max_items

                for k, v in kwarg_definition.items():
                    if hasattr(Meta, k) and v is not None:
                        meta_kwargs[k] = v
                    else:
                        meta_kwargs["extra"][k] = v

                meta_data = Meta(**meta_kwargs)

            annotation = cls._create_annotation(
                field_definition=field_definition,
                has_data_dto=has_data_dto,
                type_decoders=[*(type_decoders or []), *DEFAULT_TYPE_DECODERS],
                meta_data=meta_data,
            )

            default = field_definition.default if field_definition.has_default else NODEFAULT
            struct_fields.append((field_definition.name, annotation, default))

        return defstruct(  # type:ignore[return-value]
            f"{fn_name}_signature_model",
            struct_fields,
            bases=(cls,),
            module=getattr(fn, "__module__", None),
            namespace={
                "_return_annotation": parsed_signature.return_type.annotation,
                "_dependency_name_set": dependency_names,
                "_fields": parsed_signature.parameters,
            },
            kw_only=True,
        )

    @classmethod
    def _create_annotation(
        cls,
        field_definition: FieldDefinition,
        has_data_dto: bool,
        type_decoders: TypeDecodersSequence,
        meta_data: Meta | None = None,
    ) -> Any:
        annotation = _normalize_annotation(field_definition=field_definition, has_data_dto=has_data_dto)

        if annotation is Any:
            return annotation

        if field_definition.is_union:
            types = [
                cls._create_annotation(
                    field_definition=inner_type,
                    has_data_dto=has_data_dto,
                    type_decoders=type_decoders,
                    meta_data=meta_data,
                )
                for inner_type in (t for t in field_definition.inner_types if t.annotation is not type(None))
            ]
            return Optional[types[0]] if field_definition.is_optional else Union[tuple(types)]  # pyright: ignore

        if decoder := _get_decoder_for_type(annotation, type_decoders=type_decoders):
            # FIXME: temporary (hopefully) hack, see: https://github.com/jcrist/msgspec/issues/497
            setattr(annotation, "_decoder", decoder)

        if meta_data:
            annotation = Annotated[annotation, meta_data]  # pyright: ignore

        return annotation