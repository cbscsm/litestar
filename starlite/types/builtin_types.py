import sys
from typing import TYPE_CHECKING, Type, Union

from typing_extensions import TypeAlias  # noqa: TC002

if TYPE_CHECKING:
    from typing_extensions import _TypedDictMeta  # type: ignore

    from starlite.types.protocols import DataclassProtocol


if sys.version_info >= (3, 10):
    from types import NoneType as _NoneType
    from types import UnionType

    NoneType = _NoneType  # type: ignore[valid-type]

    UNION_TYPES = {UnionType, Union}
else:  # pragma: no cover
    UNION_TYPES = {Union}
    NoneType = type(None)

DataclassClass: TypeAlias = "Type[DataclassProtocol]"
DataclassClassOrInstance: TypeAlias = "Union[DataclassClass, DataclassProtocol]"
TypedDictClass: TypeAlias = "Type[_TypedDictMeta]"