import struct
from typing import TYPE_CHECKING

from .service import DanteUnicastService
from .util.consts import (
    NULL_HEXTET,
)
from .util.helpers import (
    encode_mac_address,
    get_mac_addr_serving_ipv4,
)

if TYPE_CHECKING:
    from .device import DanteDevice


class DanteSettingsService(DanteUnicastService):
    """
    Multicast Control and Monitoring
    """
    SERVICE_HEADER_LENGTH: int = 32
    SERVICE_PORT: int = 8700
    SERVICE_TYPE_SHORT: str = 'settings'

    async def request(
        self,
        device: DanteDevice,
        opcode: bytes,
        payload: tuple[bytes],
    ) -> bytes | None:
        ipv4 = device.ipv4
        mac_address = get_mac_addr_serving_ipv4(ipv4)
        destination = (str(ipv4), self.SERVICE_PORT)
        transaction_idx = self._transaction_index.generate()

        payload = b''.join(payload)
        message = b''.join((
            b'\xFF\xFF',
            struct.pack('>H', self.SERVICE_HEADER_LENGTH + len(payload)),
            struct.pack('>H', transaction_idx),
            NULL_HEXTET,                        # observed alternate values: \x03\xe4, \x02\x9f, \xab\xcd
            encode_mac_address(mac_address),
            NULL_HEXTET,                        # message type/direction?
            b'Audinate',                        # ~*~ magic ~*~
            b'\x07\x38',                        # possibly a protocol version; observed values: \x07\x27, \x07\x31, \x07\x34, \x07\x38
            opcode,
            NULL_HEXTET * 2,                    # second hextet sometimes observed as \x00\x64
            payload,
        ))
        return await self._protocol.request(message, destination, transaction_idx)
