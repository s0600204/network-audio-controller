import struct
from typing import TYPE_CHECKING

from .channel import DanteChannelType
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
    from .util.enums import (
        PCMEncoding,
        SampleRate,
    )


class DanteSettingsService(DanteUnicastService):
    """
    Multicast Control and Monitoring
    """
    SERVICE_HEADER_LENGTH: int = 32
    SERVICE_PORT: int = 8700
    SERVICE_TYPE_SHORT: str = 'settings'

    async def transmit(
        self,
        device: DanteDevice,
        opcode: bytes,
        payload: tuple[bytes],
    ) -> None:
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
        await self._protocol.transmit(message, destination)

    async def get_dante_model(
        self,
        device: DanteDevice,
    ) -> None:
        opcode = b'\x00\x61'
        await self.transmit(device, opcode, ())

    async def get_make_model(
        self,
        device: DanteDevice,
    ) -> None:
        opcode = b'\x00\xc1'
        await self.transmit(device, opcode, ())

    async def set_aes67(
        self,
        device: DanteDevice,
        is_enabled: bool,
    ) -> None:
        opcode = b'\x10\x06'
        payload = (
            b'\x00\x01',
            struct.pack('>H', is_enabled),
        )
        await self.transmit(device, opcode, payload)

    async def set_gain_level(
        self,
        device: DanteDevice,
        channel_type: DanteChannelType,
        channel_number: int,
        gain_level: int
    ) -> None:
        opcode = b'\x10\x0a'
        payload = (
            b'\x00\x01',
            b'\x00\x01',
            b'\x00\x0c',
            b'\x00\x10',
            b'\x01\x02' if channel_type == DanteChannelType.RX else b'\x02\x01',
            NULL_HEXTET * 2,
            struct.pack('>H', channel_number),
            NULL_HEXTET,
            struct.pack('>H', gain_level),
        )
        await self.transmit(device, opcode, payload)

    async def set_pcm_encoding(
        self,
        device: DanteDevice,
        encoding: PCMEncoding,
    ) -> None:
        opcode = b'\x00\x83'
        payload = (
            NULL_HEXTET,
            b'\x00\x01',
            encoding.encode(),
        )
        await self.transmit(device, opcode, payload)

    async def set_sample_rate(
        self,
        device: DanteDevice,
        sample_rate: SampleRate
    ) -> None:
        opcode = b'\x00\x81'
        payload = (
            NULL_HEXTET,
            b'\x00\x01',
            sample_rate.encode(),
        )
        await self.transmit(device, opcode, payload)

    async def trigger_identify(
        self,
        device: DanteDevice
    ) -> None:
        opcode = b'\x00\x63'
        await self.transmit(device, opcode, ())
