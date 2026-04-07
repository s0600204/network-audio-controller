from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import ProtocolVersion


def decode_protocol_version_from_mdns(source: bytes) -> ProtocolVersion:
    return tuple(
        int(x) for x in source.split(b".")
    )
