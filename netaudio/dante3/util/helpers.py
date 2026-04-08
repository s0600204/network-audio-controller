import codecs
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import ProtocolVersion


def decode_protocol_version_from_mdns(source: bytes) -> ProtocolVersion:
    return tuple(
        int(x) for x in source.split(b".")
    )


def encode_protocol_version(protocol_version: ProtocolVersion) -> bytes:
    return codecs.decode(
        f"{protocol_version[0]}{protocol_version[1]}{protocol_version[2]:02x}",
        "hex"
    )
