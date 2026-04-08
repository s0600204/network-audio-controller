import struct
from typing import NamedTuple, TYPE_CHECKING

from .service import (
    DanteDiscoverableService,
    DanteUnicastService,
    MessageType,
)
from .util.helpers import (
    decode_protocol_version_from_mdns,
    encode_protocol_version,
)

if TYPE_CHECKING:
    from zeroconf import ServiceInfo as MDNSServiceInfo

    from .device import DanteDevice
    from .util.types import ProtocolVersion


class DanteARCServiceDescriptor(NamedTuple):
    port: int
    protocol_version: ProtocolVersion


class DanteARCService(DanteUnicastService, DanteDiscoverableService):
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

    async def request(
        self,
        device: DanteDevice,
        opcode: bytes,
        payload: tuple[bytes],
    ) -> bytes | None:
        destination = (str(device.ipv4), device.arc.port)
        transaction_idx = self._transaction_index.generate()
        payload = b''.join(payload)
        message = b''.join((
            encode_protocol_version(device.arc.protocol_version),
            struct.pack('>H', self.SERVICE_HEADER_LENGTH + len(payload)),
            struct.pack('>H', transaction_idx),
            opcode,
            MessageType.SEND,
            payload,
        ))
        return await self._protocol.request(message, destination, transaction_idx)
