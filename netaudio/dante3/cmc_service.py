from typing import NamedTuple, TYPE_CHECKING

from .util.helpers import (
    decode_protocol_version_from_mdns,
)

if TYPE_CHECKING:
    from zeroconf import ServiceInfo as MDNSServiceInfo

    from .util.types import ProtocolVersion


class DanteCMCServiceDescriptor(NamedTuple):
    port: int
    protocol_version: ProtocolVersion


class DanteCMCService:
    """
    Dante Control Monitoring Channel
    """
    SERVICE_TYPE_MDNS: str = "_netaudio-cmc._udp.local."
    SERVICE_TYPE_SHORT: str = 'cmc'

    @classmethod
    def build_service_descriptor(cls, mdns_service_info: MDNSServiceInfo) -> DanteCMCServiceDescriptor:
        return DanteCMCServiceDescriptor(**{
            'port': mdns_service_info.port,
            'protocol_version': decode_protocol_version_from_mdns(mdns_service_info.properties[b'cmcp_vers']),
        })
