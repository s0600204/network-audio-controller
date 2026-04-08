from .consts import PYTHON_VERSION_TUPLE


if PYTHON_VERSION_TUPLE < (3, 12, 0):
    from typing import TypeAlias
    ProtocolVersion: TypeAlias = tuple[int, int, int]
    Version: TypeAlias = tuple[int, int, int] | tuple[int, int, int, int]

else:
    type ProtocolVersion = tuple[int, int, int]
    type Version = tuple[int, int, int] | tuple[int, int, int, int]
