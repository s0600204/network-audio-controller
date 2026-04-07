from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from zeroconf import ServiceInfo as MDNSServiceInfo


class DanteDBCServiceDescriptor(NamedTuple):
    port: int


class DanteDBCService:
    """
    Dante Broadcast Control Channel
    """
    SERVICE_TYPE_MDNS: str = "_netaudio-dbc._udp.local."
    SERVICE_TYPE_SHORT: str = 'dbc'

    @classmethod
    def build_service_descriptor(cls, mdns_service_info: MDNSServiceInfo) -> DanteDBCServiceDescriptor:
        return DanteDBCServiceDescriptor(**{
            'port': mdns_service_info.port,
        })
