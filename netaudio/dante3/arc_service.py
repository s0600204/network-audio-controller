from typing import NamedTuple, TYPE_CHECKING

from .util.helpers import (
    decode_protocol_version_from_mdns,
)

if TYPE_CHECKING:
    from zeroconf import ServiceInfo as MDNSServiceInfo

    from .util.types import ProtocolVersion


class DanteARCServiceDescriptor(NamedTuple):
    port: int
    protocol_version: ProtocolVersion


class DanteARCService:
    """
    Dante Audio Routing Channel
    """
    SERVICE_HEADER_LENGTH: int = 10
    SERVICE_PORT: int = 4440
    SERVICE_TYPE_MDNS: str = '_netaudio-arc._udp.local.'
    SERVICE_TYPE_SHORT: str = 'arc'

    @classmethod
    def build_service_descriptor(cls, mdns_service_info: MDNSServiceInfo) -> DanteARCServiceDescriptor:
        return DanteARCServiceDescriptor(**{
            'port': mdns_service_info.port,
            'protocol_version': decode_protocol_version_from_mdns(mdns_service_info.properties[b'arcp_vers']),
        })
